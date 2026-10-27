import httpx
import pytest

from tistory_mcp.public import (
    fetch_public_post,
    fetch_rss,
    is_login_url,
    parse_public_post,
    parse_rss,
)

RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>블로그</title><link>https://example.tistory.com/</link>
<description>d</description>
<item><title>글1</title><link>https://example.tistory.com/123</link>
<pubDate>Tue, 02 Jan 2024 10:00:00 +0900</pubDate>
<category>Dev</category><category>Notes</category><author>me</author>
<description>&lt;p&gt;본문&lt;/p&gt;</description></item>
<item><title>글2</title><link>https://example.tistory.com/122</link><description></description></item>
</channel></rss>"""

PAGE = """<html><head><title>T</title><meta property="og:title" content="OG 제목">
<meta property="article:published_time" content="2024-01-02T10:00:00+09:00">
<script>window.T.entryInfo = {"entryId":123,"isAuthor":true,
"categoryId":1,"categoryLabel":"Dev"};</script>
</head><body><div class="tt_article_useless_p_margin"><p>본문 <b>HTML</b></p></div>
<a rel="tag" href="/tag/mcp">mcp</a><a rel="tag" href="/tag/ai">ai</a></body></html>"""


def test_parse_rss():
    data = parse_rss(RSS)
    assert data["title"] == "블로그" and len(data["items"]) == 2
    first = data["items"][0]
    assert first["post_id"] == "123" and first["categories"] == ["Dev", "Notes"]
    assert first["description_html"] == "<p>본문</p>"
    assert data["items"][1]["description_html"] == ""


def test_fetch_rss_limit():
    transport = httpx.MockTransport(lambda req: httpx.Response(200, text=RSS))
    data = fetch_rss("example.tistory.com", limit=1, transport=transport)
    assert len(data["items"]) == 1


def test_parse_public_post():
    data = parse_public_post(PAGE)
    assert data["title"] == "OG 제목"
    assert data["content_html"] == "<p>본문 <b>HTML</b></p>"
    assert data["entry_info"]["entryId"] == 123
    assert data["tags"] == ["ai", "mcp"]
    assert data["published_time"].startswith("2024-01-02")


def test_fetch_public_post_sends_cookie_and_detects_login_redirect():
    seen = {}

    def handler(req: httpx.Request):
        seen["cookie"] = req.headers.get("cookie")
        return httpx.Response(200, text=PAGE)

    data = fetch_public_post(
        "example.tistory.com",
        "123",
        cookie_header="TSSESSION=x",
        transport=httpx.MockTransport(handler),
    )
    assert seen["cookie"] == "TSSESSION=x" and data["url"] == "https://example.tistory.com/123"

    def login_redirect(req: httpx.Request):
        if req.url.host == "example.tistory.com":
            return httpx.Response(
                302,
                headers={"location": "https://www.tistory.com/auth/login/?redirectUrl=x"},
            )
        return httpx.Response(200, text="<html>login</html>")

    with pytest.raises(PermissionError):
        fetch_public_post(
            "example.tistory.com", "123", transport=httpx.MockTransport(login_redirect)
        )


def test_public_page_containing_login_url_config_is_not_mistaken_for_login():
    # 실측: 공개 페이지 설정 JS 에 LOGIN_URL(/auth/login) 이 항상 포함됨.
    # 본문 마커로 판별하면 전부 오탐.
    page = PAGE.replace(
        "<title>T</title>",
        '<title>T</title><script>window.T.config = {"LOGIN_URL":'
        '"https://www.tistory.com/auth/login/?redirectUrl=https://example.tistory.com/123"};</script>',
    )
    data = fetch_public_post(
        "example.tistory.com",
        "123",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text=page)),
    )
    assert data["content_html"] == "<p>본문 <b>HTML</b></p>"


def test_is_login_url():
    assert is_login_url("https://www.tistory.com/auth/login/?redirectUrl=x")
    assert is_login_url("https://accounts.kakao.com/login?continue=x")
    assert not is_login_url("https://example.tistory.com/123")
    assert not is_login_url("https://www.tistory.com/")


def test_malformed_rss_raises_valueerror_not_parseerror():
    # ET.ParseError 는 SyntaxError 계열이라 도구 계층의 except ValueError 에 안 잡힌다
    with pytest.raises(ValueError):
        parse_rss("<rss><channel><title>x</title>")
    transport = httpx.MockTransport(lambda r: httpx.Response(200, text="<not xml"))
    with pytest.raises(ValueError):
        fetch_rss("example.tistory.com", transport=transport)
