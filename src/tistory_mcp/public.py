"""Read paths that need no login — RSS and public post pages."""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from typing import Any

import httpx
from bs4 import BeautifulSoup

from .client import USER_AGENT

CONTENT_SELECTORS = (
    ".tt_article_useless_p_margin",
    ".article",
    ".entry-content",
    '[itemprop="articleBody"]',
)
_LOGIN_HOSTS = {"www.tistory.com", "accounts.kakao.com"}
_ENTRY_INFO_RE = re.compile(r"window\.T\.entryInfo\s*=\s*(\{.*?\}|null)\s*;", re.S)


def is_login_url(url: httpx.URL | str) -> bool:
    """Whether a public-page fetch ended on a login screen, judged by the **final URL**.

    Body markers (``/auth/login`` etc.) must not be used here: every public Tistory page
    embeds ``LOGIN_URL: https://www.tistory.com/auth/login/...`` in its config script, so a
    marker check flags all of them.
    """
    u = httpx.URL(str(url))
    host = (u.host or "").lower()
    return host == "accounts.kakao.com" or (host in _LOGIN_HOSTS and u.path.startswith("/auth/"))


def _post_id_from_link(link: str) -> str | None:
    m = re.search(r"/(\d+)/?$", link or "")
    return m.group(1) if m else None


def parse_rss(xml_text: str) -> dict[str, Any]:
    # ET.ParseError 는 SyntaxError 계열이라 호출부의 `except ValueError` 에 안 잡힌다.
    # 파싱 실패를 ValueError 로 통일해 도구 계층이 한 번에 처리하게 한다.
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ValueError(f"RSS 응답이 올바른 XML 이 아닙니다: {exc}") from exc
    channel = root.find("channel")
    if channel is None:
        raise ValueError("RSS 에 channel 이 없습니다")

    def text(el: ET.Element | None, tag: str) -> str:
        node = el.find(tag) if el is not None else None
        return (node.text or "").strip() if node is not None and node.text else ""

    items = []
    for item in channel.findall("item"):
        link = text(item, "link")
        items.append(
            {
                "post_id": _post_id_from_link(link),
                "title": text(item, "title"),
                "link": link,
                "pub_date": text(item, "pubDate"),
                "author": text(item, "author"),
                "categories": [c.text.strip() for c in item.findall("category") if c.text],
                "description_html": text(item, "description"),
            }
        )
    return {
        "title": text(channel, "title"),
        "link": text(channel, "link"),
        "description": text(channel, "description"),
        "items": items,
    }


def fetch_rss(
    host: str, *, limit: int = 20, transport: httpx.BaseTransport | None = None
) -> dict[str, Any]:
    with httpx.Client(
        headers={"user-agent": USER_AGENT}, follow_redirects=True, timeout=30.0, transport=transport
    ) as http:
        res = http.get(f"https://{host}/rss")
        res.raise_for_status()
        data = parse_rss(res.text)
    data["items"] = data["items"][: max(0, limit)]
    return data


def parse_public_post(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")

    def meta(prop: str) -> str | None:
        tag = soup.find("meta", attrs={"property": prop})
        return tag.get("content") if tag and tag.get("content") else None

    content_html = None
    for sel in CONTENT_SELECTORS:
        node = soup.select_one(sel)
        if node is not None:
            content_html = node.decode_contents().strip()
            break
    entry_info = None
    m = _ENTRY_INFO_RE.search(html)
    if m and m.group(1) != "null":
        try:
            entry_info = json.loads(m.group(1))
        except ValueError:
            entry_info = None
    title = meta("og:title") or (soup.title.get_text(strip=True) if soup.title else None)
    tags = sorted(
        {a.get_text(strip=True) for a in soup.select('a[rel="tag"]') if a.get_text(strip=True)}
    )
    return {
        "title": title,
        "content_html": content_html,
        "published_time": meta("article:published_time"),
        "modified_time": meta("article:modified_time"),
        "entry_info": entry_info,
        "tags": tags,
    }


def fetch_public_post(
    host: str,
    post_id: str,
    *,
    cookie_header: str | None = None,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, Any]:
    headers = {"user-agent": USER_AGENT}
    if cookie_header:
        headers["cookie"] = cookie_header
    with httpx.Client(
        headers=headers, follow_redirects=True, timeout=30.0, transport=transport
    ) as http:
        res = http.get(f"https://{host}/{post_id}")
    if res.status_code >= 400:
        raise httpx.HTTPStatusError(
            f"공개 페이지 접근 실패 HTTP {res.status_code} (비공개/보호글이거나 없는 글)",
            request=res.request,
            response=res,
        )
    if is_login_url(res.url):
        raise PermissionError(
            "로그인 페이지로 리다이렉트됐습니다 (비공개/보호글이거나 세션이 유효하지 않음)"
        )
    data = parse_public_post(res.text)
    data["url"] = str(res.url)
    return data
