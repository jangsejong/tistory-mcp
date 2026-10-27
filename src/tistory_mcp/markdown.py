"""Markdown → Tistory-safe HTML.

Tistory does not render markdown, so the tool converts it before sending. Sanitizing follows
the attribute whitelist observed on real posts and strips script/on* vectors.
Image substitutions `[##_Image|kage@...|CDM|1.3|{json}_##]` are validated against the exact
shape produced by ``tistory_upload_image``, swapped for a nonce placeholder before rendering
and restored verbatim afterwards (they must stay byte-identical to ``attachments``).
Editor styling attributes (data-ke-*) are added on the markdown path only; the HTML path is
sanitized as written.
"""

from __future__ import annotations

import logging
import re
import secrets

import nh3
from markdown_it import MarkdownIt

from .client import IMAGE_STYLES

log = logging.getLogger("tistory_mcp.markdown")

CONTENT_FORMATS = ("markdown", "html")

# Anything that looks like a substitution is a candidate; each candidate must then match the
# strict shape exactly, otherwise the whole content is rejected (a lax match would let the
# inner text bypass sanitizing, because placeholders are restored *after* nh3).
_IMAGE_SUB_CANDIDATE_RE = re.compile(r"\[##_Image\|[\s\S]*?_##\]")
_IMAGE_SUB_STRICT_RE = re.compile(
    r"\[##_Image\|kage@[^\r\n\t|<>\"'`{}\[\]\\]+\|CDM\|1\.3\|"
    r'\{"originWidth":\d{1,6},"originHeight":\d{1,6},"style":"(?:'
    + "|".join(re.escape(s) for s in IMAGE_STYLES)
    + r')"\}_##\]'
)

ALLOWED_TAGS: set[str] = {
    "h1", "h2", "h3", "h4", "h5", "h6",
    "p", "div", "span", "br", "hr",
    "strong", "b", "em", "i", "u", "s", "del", "ins", "mark", "sub", "sup", "small",
    "blockquote", "q", "cite",
    "ul", "ol", "li", "dl", "dt", "dd",
    "pre", "code", "kbd", "samp", "var",
    "table", "thead", "tbody", "tfoot", "tr", "th", "td", "caption", "colgroup", "col",
    "a", "img", "figure", "figcaption", "picture", "source", "iframe",
    "abbr", "address", "time", "details", "summary",
}  # fmt: skip
ALLOWED_ATTRIBUTES: dict[str, set[str]] = {
    "h1": {"id"}, "h2": {"id"}, "h3": {"id"}, "h4": {"id"}, "h5": {"id"}, "h6": {"id"},
    "a": {"href", "name", "target", "rel", "title"},
    "img": {"src", "alt", "title", "width", "height", "loading"},
    "source": {"src", "srcset", "type", "media"},
    "span": {"style", "class"},
    "div": {"class", "style"},
    "p": {"class", "style"},
    "figure": {"class"},
    "figcaption": {"class"},
    "blockquote": {"class", "cite"},
    "pre": {"class"},
    "code": {"class"},
    "table": {"class", "style"},
    "th": {"colspan", "rowspan", "scope", "style"},
    "td": {"colspan", "rowspan", "style"},
    "col": {"span", "style"},
    "iframe": {"src", "width", "height", "frameborder", "allow", "allowfullscreen", "title"},
    "time": {"datetime"},
    "abbr": {"title"},
    "ol": {"start", "type"},
}  # fmt: skip
ALLOWED_STYLE_PROPERTIES: set[str] = {
    "color", "background-color", "text-align", "font-weight", "font-size", "font-style",
    "text-decoration", "width", "height", "max-width", "list-style-type", "border",
    "padding", "margin",
}  # fmt: skip
URL_SCHEMES: set[str] = {"http", "https", "mailto", "tel"}

_md = MarkdownIt("commonmark", {"breaks": True, "html": True}).enable(["table", "strikethrough"])

# Attributes the Tistory editor puts on its own output. The blog's content.css keys its
# rules for dividers, quotes, lists and headings on these selectors, so markdown-rendered
# posts look different without them. They are added *before* sanitizing so nh3 stays the
# last gate, and only whitelisted values are used — re-sending the result as html is a no-op.
# Only attribute-less tags are touched (ol keeps the `start` that markdown-it adds).
_EDITOR_STYLE = (
    ("<p>", '<p data-ke-size="size16">'),
    ("<h2>", '<h2 data-ke-size="size26">'),
    ("<h3>", '<h3 data-ke-size="size23">'),
    ("<h4>", '<h4 data-ke-size="size20">'),
    ("<blockquote>", '<blockquote data-ke-style="style1">'),
    ("<table>", '<table style="width:100%" data-ke-align="alignLeft">'),
)
_HR_RE = re.compile(r"<hr\s*/?>")
_LIST_TAG_RE = re.compile(r"<(/?)(ul|ol)\b([^>]*)>")
_OL_START_RE = re.compile(r'\s+start="\d+"')
# content.css sets bullets per ul[data-ke-list-type]; follow the browser defaults by depth
# (disc → circle → square). Depth counts ul and ol together.
_UL_KINDS = ("disc", "circle", "square")


class InvalidImageSubstitutionError(ValueError):
    """An image substitution does not match the shape produced by tistory_upload_image."""


def _placeholder(nonce: str, i: int) -> str:
    return f"TISTORYIMG{nonce}N{i}X"


def _protect(text: str) -> tuple[str, str, list[str]]:
    nonce = secrets.token_hex(8)
    subs: list[str] = []

    def repl(m: re.Match[str]) -> str:
        sub = m.group(0)
        if not _IMAGE_SUB_STRICT_RE.fullmatch(sub):
            raise InvalidImageSubstitutionError(
                "이미지 치환자 형식이 올바르지 않습니다. tistory_upload_image 가 돌려준 "
                f"substitution 을 글자 그대로 넣으세요 (받은 값 앞부분: {sub[:60]!r})"
            )
        subs.append(sub)
        return _placeholder(nonce, len(subs) - 1)

    return _IMAGE_SUB_CANDIDATE_RE.sub(repl, text), nonce, subs


def _restore(html: str, nonce: str, subs: list[str]) -> str:
    for i, sub in enumerate(subs):
        token = _placeholder(nonce, i)
        if token not in html:
            log.warning("이미지 치환자 %d 이(가) 변환 중 사라졌습니다 (script 등 제거 영역 안?)", i)
        html = html.replace(token, sub)
    return html


def sanitize_html(html: str) -> str:
    return nh3.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        generic_attribute_prefixes={"data-"},
        url_schemes=URL_SCHEMES,
        filter_style_properties=ALLOWED_STYLE_PROPERTIES,
        link_rel=None,
    )


def _style_lists(html: str) -> str:
    depth = 0

    def repl(m: re.Match[str]) -> str:
        nonlocal depth
        close, tag, attrs = m.groups()
        if close:
            depth = max(depth - 1, 0)
            return m.group(0)
        depth += 1
        if tag == "ul" and not attrs:
            kind = _UL_KINDS[min(depth, len(_UL_KINDS)) - 1]
            return f'<ul data-ke-list-type="{kind}">'
        if tag == "ol" and (not attrs or _OL_START_RE.fullmatch(attrs)):
            return f'<ol{attrs} data-ke-list-type="decimal">'
        return m.group(0)

    return _LIST_TAG_RE.sub(repl, html)


def apply_editor_style(html: str) -> str:
    for plain, styled in _EDITOR_STYLE:
        html = html.replace(plain, styled)
    return _style_lists(_HR_RE.sub('<hr data-ke-style="style1">', html))


def markdown_to_html(markdown: str) -> str:
    text, nonce, subs = _protect(markdown)
    return _restore(sanitize_html(apply_editor_style(_md.render(text))), nonce, subs)


def sanitize_content_html(html: str) -> str:
    text, nonce, subs = _protect(html)
    return _restore(sanitize_html(text), nonce, subs)


def render_content(content: str, content_format: str) -> str:
    if content_format == "markdown":
        return markdown_to_html(content)
    if content_format == "html":
        return sanitize_content_html(content)
    raise ValueError(f"content_format 은 {CONTENT_FORMATS} 중 하나여야 합니다: {content_format!r}")
