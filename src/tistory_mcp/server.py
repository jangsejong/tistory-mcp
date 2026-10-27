"""MCP server entry point — tool definitions, input validation and error translation only.

Endpoint knowledge lives in client.py. Running the module without arguments starts the stdio
server; a few subcommands (install-browser, login, status, logout) exist for terminal use.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal

import httpx
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from . import __version__
from .auth import LoginError, login_interactive
from .client import (
    IMAGE_STYLES,
    VISIBILITY_FROM_RESPONSE,
    VISIBILITY_TO_INT,
    SessionExpiredError,
    TistoryApiError,
    TistoryClient,
    build_attachment_ref,
    build_image_substitution,
    validate_post_id,
)
from .config import InvalidHostError, normalize_host, settings, validate_cdp_url
from .images import image_dimensions
from .markdown import render_content
from .public import fetch_public_post, fetch_rss
from .ratelimit import RateLimiter, RateLimitError
from .session import SessionStore, SessionStoreError, cookie_header, earliest_expiry

log = logging.getLogger("tistory_mcp")

REPO_URL = "https://github.com/jangsejong/tistory-mcp"
Visibility = Literal["public", "private", "protected"]
ContentFormat = Literal["markdown", "html"]
ImageStyle = Literal[IMAGE_STYLES]

_BLOG_URL = Field(description="Blog host or URL (블로그 주소). e.g. myblog.tistory.com")

_READ = ToolAnnotations(
    read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=True
)
_WRITE = ToolAnnotations(
    read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=True
)
_DESTRUCTIVE = ToolAnnotations(
    read_only_hint=False, destructive_hint=True, idempotent_hint=True, open_world_hint=True
)

INSTRUCTIONS = (
    "Unofficial tools for a Tistory (티스토리, Korean blog service) blog, via its admin API "
    "with a saved login session. "
    "1) If a tool reports a missing or expired session, call tistory_session_init and tell the "
    "user to finish the Kakao login and the KakaoTalk push approval in the browser window "
    "(or run `tistory-mcp login <blog>` in a terminal). "
    "2) `category` is an integer id — look it up with tistory_get_categories first. "
    "3) tistory_publish_post ALWAYS creates a new post and defaults to private (비공개). "
    "Never auto-retry it after an error or timeout; check tistory_list_posts first. "
    "Use visibility='public' only when the user explicitly asks to publish publicly. "
    "4) Markdown content is converted to HTML by the tool (Tistory does not render markdown). "
    "tistory_update_post defaults to content_format='html'. "
    "5) Images: upload with tistory_upload_image, paste its `substitution` verbatim into the "
    "content and pass `attachment_ref` in `attachments`, otherwise the image breaks later. "
    "6) Deleting is permanent — confirm with the user in chat before calling with confirm=true. "
    "7) Publish/update are rate-limited (default: 60 s apart, 20 per day). "
    "8) tistory_fetch_public_posts needs no login."
)

server = MCPServer(
    name="tistory-mcp",
    title="Tistory MCP (Unofficial)",
    version=__version__,
    website_url=REPO_URL,
    instructions=INSTRUCTIONS,
)


# ── helpers ──────────────────────────────────────────────────────────────────
def _host(blog_url: str) -> str:
    try:
        return normalize_host(blog_url)
    except InvalidHostError as exc:
        raise ToolError(str(exc)) from exc


def _client(blog_url: str) -> TistoryClient:
    host = _host(blog_url)
    try:
        session = SessionStore().load(host)
    except SessionStoreError as exc:
        raise ToolError(str(exc)) from exc
    if session is None:
        raise ToolError(
            f"{host} 의 저장된 세션이 없습니다. tistory_session_init 을 먼저 실행하세요."
        )
    header = cookie_header(session.cookies, host)
    if not header:
        raise ToolError(
            f"{host} 의 쿠키가 모두 만료되었습니다. tistory_session_init 을 다시 실행하세요."
        )
    return TistoryClient(host, header)


def _translate(exc: Exception) -> ToolError:
    # A ToolError raised by a tool itself passes through (else it would be double-wrapped).
    if isinstance(exc, ToolError):
        return exc
    if isinstance(exc, SessionExpiredError | RateLimitError | ValueError):
        return ToolError(str(exc))
    if isinstance(exc, TistoryApiError):
        detail = f" | {exc.body}" if exc.body else ""
        return ToolError(f"{exc}{detail}")
    return ToolError(f"{exc.__class__.__name__}: {exc}")


def _iso(ts: float | None) -> str | None:
    return datetime.fromtimestamp(ts, tz=UTC).isoformat() if ts else None


def _rate_limiter() -> RateLimiter:
    cfg = settings()
    return RateLimiter(
        cfg.ratelimit_path, min_interval_sec=cfg.min_interval_sec, daily_cap=cfg.daily_cap
    )


def _flatten_categories(nodes: list[dict], parent_id: int = 0, depth: int = 1) -> list[dict]:
    out: list[dict] = []
    for n in nodes or []:
        out.append(
            {
                "id": n.get("id"),
                "name": n.get("name"),
                "parent_id": parent_id,
                "depth": depth,
                "entries": n.get("entries"),
                "visibility": n.get("visibility"),
            }
        )
        out.extend(_flatten_categories(n.get("children") or [], int(n.get("id") or 0), depth + 1))
    return out


def _join_tags(tags: list[str] | None) -> str:
    """Tistory's ``tag`` body field is comma-separated; empty tags are dropped."""
    return ",".join(t.strip() for t in (tags or []) if t.strip())


def _simplify_post(item: dict) -> dict:
    return {
        "id": item.get("id"),
        "title": item.get("title"),
        "visibility": VISIBILITY_FROM_RESPONSE.get(
            str(item.get("visibility")), item.get("visibility")
        ),
        "category": item.get("category"),
        "category_id": item.get("categoryId"),
        "published": item.get("published"),
        "modified": item.get("modified"),
        "permalink": item.get("permalink"),
        "is_scheduled": item.get("isScheduled"),
        "reserved_date": item.get("reservedDate"),
        "comments": item.get("countOfComments"),
    }


# ── session ──────────────────────────────────────────────────────────────────
@server.tool(title="Log in to Tistory (로그인)", annotations=_WRITE)
async def tistory_session_init(
    blog_url: Annotated[str, _BLOG_URL],
    timeout_sec: Annotated[
        int, Field(ge=30, le=1800, description="How long to wait for the login (seconds)")
    ] = 300,
    cdp_url: Annotated[
        str | None,
        Field(
            description="CDP address of a browser that is already running with "
            "--remote-debugging-port, e.g. http://127.0.0.1:9222. Use when no browser window "
            "can be shown (WSL, SSH, containers)"
        ),
    ] = None,
) -> dict[str, Any]:
    """Open a browser for the Kakao login (카카오 로그인 + 카카오톡 승인) and save the cookies.

    Blocks until the user finishes or timeout_sec passes — tell the user to look for the browser
    window and approve the KakaoTalk push before calling. The KakaoTalk 2-factor approval cannot
    be automated. Once saved, other tools work without a browser until the session expires
    (days to weeks); call again when a tool reports an expired session.
    """
    host = _host(blog_url)
    cfg = settings()
    cdp = cdp_url or cfg.cdp_url
    if cdp:
        try:
            cdp = validate_cdp_url(cdp)
        except InvalidHostError as exc:
            raise ToolError(str(exc)) from exc
    try:
        session = await login_interactive(host, timeout_sec=timeout_sec, cdp_url=cdp)
    except LoginError as exc:
        raise ToolError(str(exc)) from exc
    try:
        location = SessionStore(cfg).save(session)
    except SessionStoreError as exc:
        raise ToolError(str(exc)) from exc
    return {
        "host": host,
        "cookie_count": len(session.cookies),
        "earliest_expiry": _iso(earliest_expiry(session.cookies, host)),
        "stored_at": location,
        "source": session.source,
    }


@server.tool(title="Session status (세션 상태)", annotations=_READ)
def tistory_session_status(blog_url: Annotated[str, _BLOG_URL]) -> dict[str, Any]:
    """Report whether a saved session exists, when it was saved and when it expires.

    Also makes one admin API call to tell whether it is live right now (valid/expired).
    """
    host = _host(blog_url)
    try:
        session = SessionStore().load(host)
    except SessionStoreError as exc:
        raise ToolError(str(exc)) from exc
    if session is None:
        return {"host": host, "exists": False, "live": "none"}
    header = cookie_header(session.cookies, host)
    result: dict[str, Any] = {
        "host": host,
        "exists": True,
        "saved_at": _iso(session.saved_at),
        "earliest_expiry": _iso(earliest_expiry(session.cookies, host)),
        "cookie_names": sorted({str(c.get("name")) for c in session.cookies}),
        "source": session.source,
    }
    if not header:
        result["live"] = "expired"
        return result
    try:
        with TistoryClient(host, header) as c:
            c.get_categories()
        result["live"] = "valid"
    except SessionExpiredError:
        result["live"] = "expired"
    except TistoryApiError as exc:
        result["live"] = f"error: {exc}"
    return result


# ── read ─────────────────────────────────────────────────────────────────────
@server.tool(title="List categories (카테고리)", annotations=_READ)
def tistory_get_categories(blog_url: Annotated[str, _BLOG_URL]) -> dict[str, Any]:
    """Return the category tree flattened to id / name / parent id.

    Use the integer id here as `category` when publishing or updating (names are not accepted).
    """
    try:
        with _client(blog_url) as c:
            data = c.get_categories()
    except Exception as exc:
        raise _translate(exc) from exc
    return {
        "root_label": data.get("rootLabel"),
        "categories": _flatten_categories(data.get("categories") or []),
    }


@server.tool(title="List posts (글 목록)", annotations=_READ)
def tistory_list_posts(
    blog_url: Annotated[str, _BLOG_URL],
    page: Annotated[int, Field(ge=1, le=1000, description="Page number, 1-based")] = 1,
    keyword: Annotated[
        str, Field(description="Server-side search keyword; empty string = all posts")
    ] = "",
    search_type: Annotated[
        Literal["title", "content", "tag"],
        Field(description="Where to search the keyword: post title, body, or tag"),
    ] = "title",
    visibility: Annotated[
        Literal["all", "public", "private", "protected"], Field(description="Visibility filter")
    ] = "all",
    category: Annotated[int, Field(description="Category id filter; -3 = all categories")] = -3,
) -> dict[str, Any]:
    """List posts from the admin side (includes private and protected posts), one page at a time.

    Bodies are not included — use tistory_get_post for the body.
    """
    try:
        with _client(blog_url) as c:
            data = c.list_posts(
                category=category,
                page=page,
                keyword=keyword,
                search_type=search_type,
                visibility=visibility,
            )
    except Exception as exc:
        raise _translate(exc) from exc
    items = data.get("items") or []
    meta = {k: v for k, v in data.items() if k != "items"}
    return {
        "page": page,
        "count": len(items),
        "items": [_simplify_post(i) for i in items],
        "meta": meta,
    }


@server.tool(title="Get a post (글 조회)", annotations=_READ)
def tistory_get_post(
    blog_url: Annotated[str, _BLOG_URL],
    post_id: Annotated[str, Field(description="Post number (글 번호), digits only")],
) -> dict[str, Any]:
    """Return one post's metadata (from the admin list) and its body HTML (from the post page).

    Works for private posts with the saved session. The body is the skin-rendered HTML, not the
    original markdown (Tistory keeps no markdown). To edit, write the new body yourself and send
    it with tistory_update_post rather than echoing content_html back.
    """
    try:
        pid = validate_post_id(post_id)
        with _client(blog_url) as c:
            meta = c.find_post(pid)
            host, cookie = c.host, c.cookie_header
    except Exception as exc:
        raise _translate(exc) from exc
    result: dict[str, Any] = {"meta": _simplify_post(meta) if meta else None}
    if meta is None:
        # Outside the admin-list scan window (recent 20 pages) the body is still readable.
        result["meta_note"] = f"글 {pid} 이(가) 관리자 목록 최근 페이지에 없어 메타는 생략했습니다"
    try:
        page = fetch_public_post(host, pid, cookie_header=cookie)
        result.update(
            {
                "title": page.get("title"),
                "content_html": page.get("content_html"),
                "tags": page.get("tags"),
                "published_time": page.get("published_time"),
                "url": page.get("url"),
            }
        )
    except (httpx.HTTPError, PermissionError, ValueError) as exc:
        result["content_html"] = None
        result["content_note"] = f"본문 조회 실패: {exc}"
    return result


@server.tool(title="Fetch public posts via RSS (공개 글 RSS)", annotations=_READ)
def tistory_fetch_public_posts(
    blog_url: Annotated[str, _BLOG_URL],
    limit: Annotated[int, Field(ge=1, le=50, description="Max items to return")] = 20,
    include_content: Annotated[
        bool, Field(description="Include each item's RSS description (body HTML)")
    ] = False,
) -> dict[str, Any]:
    """Fetch the latest public posts of any Tistory blog from its RSS feed. No login needed."""
    host = _host(blog_url)
    try:
        data = fetch_rss(host, limit=limit)
    except (httpx.HTTPError, ValueError) as exc:
        raise ToolError(f"RSS 조회 실패: {exc}") from exc
    items = data["items"]
    if not include_content:
        items = [{k: v for k, v in i.items() if k != "description_html"} for i in items]
    return {"blog_title": data["title"], "link": data["link"], "count": len(items), "items": items}


# ── write ────────────────────────────────────────────────────────────────────
def _prepare_body(
    *,
    title: str,
    content: str,
    content_format: str,
    category: int,
    tags: list[str] | None,
    visibility: str,
    password: str | None,
    slogan: str,
    attachments: list[str] | None,
    post_type: str,
) -> dict[str, Any]:
    if not title.strip():
        raise ToolError("title 이 비어 있습니다")
    if visibility == "protected" and not password:
        raise ToolError("visibility='protected' 는 password 가 필요합니다")
    if visibility not in VISIBILITY_TO_INT:
        raise ToolError(
            f"visibility 는 public/private/protected 중 하나여야 합니다: {visibility!r}"
        )
    try:
        html = render_content(content, content_format)
    except ValueError as exc:
        raise ToolError(str(exc)) from exc
    return {
        "title": title,
        "content": html,
        "slogan": slogan or "",
        "visibility": VISIBILITY_TO_INT[visibility],
        "category": max(0, int(category)),
        "tag": _join_tags(tags),
        "password": password or "",
        "type": post_type,
        "attachments": list(attachments or []),
    }


@server.tool(title="Publish a new post (새 글 발행)", annotations=_WRITE)
def tistory_publish_post(
    blog_url: Annotated[
        str, Field(description="Target blog host or URL — required to prevent mis-publishing")
    ],
    title: Annotated[str, Field(description="Post title (제목)")],
    content: Annotated[
        str,
        Field(
            description="Post body. Markdown by default (converted to HTML by the tool). "
            "For images, paste the `substitution` from tistory_upload_image verbatim"
        ),
    ],
    content_format: Annotated[
        ContentFormat, Field(description="'markdown' (default) or 'html'")
    ] = "markdown",
    category: Annotated[
        int, Field(ge=0, description="Category id from tistory_get_categories; 0 = none")
    ] = 0,
    tags: Annotated[
        list[str] | None,
        Field(description="Tags (태그), one per item, without '#' and without commas"),
    ] = None,
    visibility: Annotated[
        Visibility,
        Field(
            description="Default 'private' (비공개). Use 'public' only when the user explicitly "
            "asks; 'protected' needs password"
        ),
    ] = "private",
    password: Annotated[
        str | None, Field(description="Password for visibility='protected'")
    ] = None,
    slogan: Annotated[
        str, Field(description="URL slug; empty = generated from the title by the server")
    ] = "",
    attachments: Annotated[
        list[str] | None,
        Field(
            description="attachment_ref of every image used in content (from tistory_upload_image)"
        ),
    ] = None,
    post_type: Annotated[
        Literal["post", "page"], Field(description="'post' (default) or a static 'page'")
    ] = "post",
) -> dict[str, Any]:
    """Create a NEW post. Every call creates a new post — this is not a draft and not an update.

    Do not retry after an error or timeout without checking tistory_list_posts first, or the post
    may be duplicated. Defaults to private so the user can review it before switching to public
    with tistory_update_post. Rate-limited (default 60 s apart, 20 per day).
    """
    body = _prepare_body(
        title=title,
        content=content,
        content_format=content_format,
        category=category,
        tags=tags,
        visibility=visibility,
        password=password,
        slogan=slogan,
        attachments=attachments,
        post_type=post_type,
    )
    try:
        with _client(blog_url) as c:
            _rate_limiter().check_and_record("publish")
            result = c.publish_post(body)
    except Exception as exc:
        raise _translate(exc) from exc
    out: dict[str, Any] = {**result, "visibility": visibility, "category": body["category"]}
    if visibility == "public":
        out["warning"] = "전체 공개로 발행되었습니다"
    return out


@server.tool(title="Update a post (글 수정)", annotations=_WRITE)
def tistory_update_post(
    blog_url: Annotated[str, Field(description="Blog host or URL of the post to update")],
    post_id: Annotated[str, Field(description="Post number (글 번호)")],
    content: Annotated[
        str,
        Field(
            description="The complete new body — the server overwrites the whole post. "
            "Do not echo content_html from tistory_get_post; write the new body yourself"
        ),
    ],
    content_format: Annotated[
        ContentFormat,
        Field(
            description="Default 'html'. Set 'markdown' when sending markdown, or it is posted "
            "as raw text"
        ),
    ] = "html",
    title: Annotated[
        str | None, Field(description="New title; omit to keep the current one")
    ] = None,
    category: Annotated[
        int | None, Field(ge=0, description="New category id; omit to keep the current one")
    ] = None,
    tags: Annotated[
        list[str] | None,
        Field(
            description="New tags; omit to keep the current tags (read from the post page), "
            "pass [] to clear"
        ),
    ] = None,
    visibility: Annotated[
        Visibility | None,
        Field(description="New visibility; omit to keep the current one. 'public' makes it live"),
    ] = None,
    password: Annotated[
        str | None, Field(description="Password for visibility='protected'")
    ] = None,
    slogan: Annotated[str | None, Field(description="New URL slug; omit to keep")] = None,
    attachments: Annotated[
        list[str] | None,
        Field(description="attachment_ref of images used in the new content"),
    ] = None,
) -> dict[str, Any]:
    """Update an existing post. The body must be sent in full (the server does not merge).

    Title, category, visibility and slug keep their current values when omitted; tags are kept by
    reading them from the post page (pass [] to clear). Rate-limited together with publish.
    """
    if not content.strip():
        raise ToolError("content 가 비어 있습니다. 빈 본문으로 덮어쓰기를 막기 위해 거부합니다")
    try:
        pid = validate_post_id(post_id)
        with _client(blog_url) as c:
            current = c.find_post(pid)
            if current is None:
                raise ToolError(f"글 {pid} 을(를) 찾지 못했습니다")
            host = c.host
            if tags is None:
                try:
                    page = fetch_public_post(host, pid, cookie_header=c.cookie_header)
                    tags = page.get("tags") or []
                except (httpx.HTTPError, PermissionError, ValueError) as exc:
                    raise ToolError(
                        f"현재 태그를 읽지 못해 보존할 수 없습니다({exc}). "
                        "tags 를 명시하세요(비우려면 [])"
                    ) from exc
            cur_vis = VISIBILITY_FROM_RESPONSE.get(str(current.get("visibility")), "private")
            body = _prepare_body(
                title=title if title is not None else str(current.get("title") or ""),
                content=content,
                content_format=content_format,
                category=category if category is not None else int(current.get("categoryId") or 0),
                tags=tags,
                visibility=visibility or cur_vis,
                password=password,
                slogan=slogan if slogan is not None else str(current.get("slogan") or ""),
                attachments=attachments,
                post_type="post",
            )
            _rate_limiter().check_and_record("update")
            result = c.update_post(pid, body)
    except Exception as exc:
        raise _translate(exc) from exc
    return {**result, "visibility": visibility or cur_vis, "tags": tags}


@server.tool(title="Delete a post (글 삭제)", annotations=_DESTRUCTIVE)
def tistory_delete_post(
    blog_url: Annotated[str, Field(description="Blog host or URL of the post to delete")],
    post_id: Annotated[str, Field(description="Post number (글 번호)")],
    confirm: Annotated[
        bool,
        Field(description="Must be true to actually delete. Ask the user in chat first"),
    ] = False,
) -> dict[str, Any]:
    """Permanently delete a post. Cannot be undone.

    Ask the user to confirm in chat, then call with confirm=true.
    """
    if not confirm:
        raise ToolError("삭제는 되돌릴 수 없습니다. 사용자 확인 후 confirm=true 로 다시 호출하세요")
    try:
        pid = validate_post_id(post_id)
        with _client(blog_url) as c:
            data = c.delete_post(pid)
    except Exception as exc:
        raise _translate(exc) from exc
    return {"deleted_post_id": pid, "response": data}


@server.tool(title="Upload an image (이미지 업로드)", annotations=_WRITE)
def tistory_upload_image(
    blog_url: Annotated[str, _BLOG_URL],
    file_path: Annotated[
        str, Field(description="Local image path (png/jpg/jpeg/gif/webp, up to 20MB)")
    ],
    width: Annotated[
        int | None, Field(ge=0, description="Pixel width; read from the file header if omitted")
    ] = None,
    height: Annotated[
        int | None, Field(ge=0, description="Pixel height; read from the file header if omitted")
    ] = None,
    style: Annotated[
        ImageStyle,
        Field(description="Alignment: alignCenter (default), alignLeft, alignRight, widthOrigin"),
    ] = "alignCenter",
) -> dict[str, Any]:
    """Upload an image and return `substitution` (paste into the body) and `attachment_ref`.

    Put `substitution` verbatim where the image goes, and pass `attachment_ref` in `attachments`
    when publishing/updating — otherwise the image is garbage-collected after about 15 days.
    Do not put the returned URL into the body directly.
    """
    if width is None or height is None:
        # Only the header is needed; the upload path reads the file again in full.
        # A JPEG whose EXIF/ICC exceeds 64KB may not expose its SOF here, leaving 0.
        try:
            with Path(file_path).expanduser().open("rb") as f:
                dims = image_dimensions(f.read(65536))
        except OSError:
            dims = None
        # Only fill the side the user did not specify.
        if width is None:
            width = dims[0] if dims else 0
        if height is None:
            height = dims[1] if dims else 0
    try:
        with _client(blog_url) as c:
            upload = c.upload_image(file_path)
    except Exception as exc:
        raise _translate(exc) from exc
    ref = build_attachment_ref(upload)
    return {
        "attachment_ref": ref,
        "substitution": build_image_substitution(ref, width, height, style),
        "key": upload.get("key"),
        "filename": upload.get("filename"),
        "size": upload.get("size"),
        "width": width,
        "height": height,
    }


@server.tool(title="Save autosave draft (자동저장 초안)", annotations=_WRITE)
def tistory_save_draft(
    blog_url: Annotated[str, _BLOG_URL],
    title: Annotated[str, Field(description="Draft title")],
    content: Annotated[str, Field(description="Draft body (markdown by default)")],
    content_format: Annotated[
        ContentFormat, Field(description="'markdown' (default) or 'html'")
    ] = "markdown",
    category: Annotated[int, Field(ge=0, description="Category id; 0 = none")] = 0,
    tags: Annotated[list[str] | None, Field(description="Tags, one per item")] = None,
    attachments: Annotated[
        list[str] | None, Field(description="attachment_ref of images used in content")
    ] = None,
) -> dict[str, Any]:
    """Write a draft into the editor's single autosave slot. No post is created.

    The next time the user opens the editor it offers to restore this draft. There is only one
    slot, so saving again overwrites the previous draft. For several reviewable drafts, publish
    with visibility='private' instead.
    """
    try:
        html = render_content(content, content_format)
        with _client(blog_url) as c:
            c.save_autosave(
                title=title,
                content=html,
                tags=_join_tags(tags),
                category_id=category,
                attachments=attachments,
            )
    except Exception as exc:
        raise _translate(exc) from exc
    return {"saved": True, "slot": "autosave", "note": "단일 슬롯 — 다음 저장 시 덮어씀"}


# ── CLI ──────────────────────────────────────────────────────────────────────
def _setup_logging() -> None:
    level = getattr(logging, settings().log_level.upper(), None)
    level = level if isinstance(level, int) else logging.INFO
    logging.basicConfig(
        stream=sys.stderr, level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    # httpx logs every request URL at INFO; keep that for DEBUG runs only.
    logging.getLogger("httpx").setLevel(
        min(level, logging.DEBUG) if level <= logging.DEBUG else logging.WARNING
    )


def _run_server() -> None:
    _setup_logging()
    log.info("tistory-mcp %s stdio 시작", __version__)
    server.run(transport="stdio")


def _cmd_install_browser(args: argparse.Namespace) -> int:
    # Same interpreter as this package, so the browser revision matches the installed playwright.
    cmd = [sys.executable, "-m", "playwright", "install", "chromium"]
    print("$ " + " ".join(cmd), file=sys.stderr)
    return subprocess.run(cmd, stdin=subprocess.DEVNULL).returncode


def _cmd_login(args: argparse.Namespace) -> int:
    try:
        result = asyncio.run(
            tistory_session_init(args.blog_url, timeout_sec=args.timeout, cdp_url=args.cdp_url)
        )
    except ToolError as exc:
        print(f"로그인 실패: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    try:
        result = tistory_session_status(args.blog_url)
    except ToolError as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _cmd_logout(args: argparse.Namespace) -> int:
    try:
        host = _host(args.blog_url)
        removed = SessionStore().delete(host)
    except (ToolError, SessionStoreError) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1
    print(f"{host}: {'세션을 삭제했습니다' if removed else '저장된 세션이 없습니다'}")
    return 0 if removed else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tistory-mcp",
        description="Unofficial MCP server for Tistory blogs. "
        "Without a command it runs the stdio MCP server (인자 없이 실행하면 MCP 서버).",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", metavar="command")
    sub.add_parser("serve", help="run the stdio MCP server (default)")
    sub.add_parser("install-browser", help="download Chromium for the login window (once, ~300MB)")
    login = sub.add_parser("login", help="log in from the terminal and save the session")
    login.add_argument("blog_url", help="e.g. myblog.tistory.com")
    login.add_argument("--cdp-url", help="attach to a running browser, e.g. http://127.0.0.1:9222")
    login.add_argument("--timeout", type=int, default=300, help="seconds to wait (default 300)")
    status = sub.add_parser("status", help="show the saved session and whether it is live")
    status.add_argument("blog_url")
    logout = sub.add_parser("logout", help="delete the saved session for a blog")
    logout.add_argument("blog_url")
    return p


_COMMANDS = {
    "install-browser": _cmd_install_browser,
    "login": _cmd_login,
    "status": _cmd_status,
    "logout": _cmd_logout,
}


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.command in (None, "serve"):
        _run_server()
        return
    _setup_logging()
    raise SystemExit(_COMMANDS[args.command](args))


if __name__ == "__main__":
    main()
