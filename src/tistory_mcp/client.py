"""Adapter for the Tistory admin JSON API (httpx).

This is an *unofficial* API. Every URL, body schema and response interpretation lives in this
file only, so a change on Tistory's side is repaired here. The endpoint baseline follows the
observations documented in kim-se-hee/tistory-mcp (``docs/api.md``, MIT).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from . import __version__

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    f"Chrome/128.0.0.0 Safari/537.36 tistory-mcp/{__version__}"
)
# Markers for an expired session that comes back as 200 + login HTML instead of a 302.
LOGIN_MARKERS = (
    "accounts.kakao.com",
    "/auth/login",
    "/auth/kakao",
    'id="loginKey"',
    "kakao_login",
    "tistory-oauth",
)
VISIBILITY_TO_INT: dict[str, int] = {"private": 0, "protected": 15, "public": 20}
VISIBILITY_FROM_INT: dict[int, str] = {v: k for k, v in VISIBILITY_TO_INT.items()}
VISIBILITY_FROM_RESPONSE: dict[str, str] = {
    "PRIVATE": "private",
    "PROTECTED": "protected",
    "PUBLIC": "public",
}
# posts.json filter vocabulary (observed; the server answers 400 to anything else).
LIST_VISIBILITY_PARAM: dict[str, str] = {
    "all": "all",
    "public": "visible",
    "private": "hidden",
    "protected": "protect",
}
LIST_SEARCH_TYPES: tuple[str, ...] = ("title", "content", "tag")
ALLOWED_IMAGE_MIMES: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}
MAX_IMAGE_BYTES = 20 * 1024 * 1024
# Alignment values the editor accepts in the image substitution JSON.
IMAGE_STYLES: tuple[str, ...] = ("alignCenter", "alignLeft", "alignRight", "widthOrigin")
_POST_ID_RE = re.compile(r"^\d{1,12}$")


class TistoryError(Exception):
    """어댑터 공통 베이스."""


class SessionExpiredError(TistoryError):
    def __init__(
        self,
        message: str = "티스토리 세션이 없거나 만료되었습니다. tistory_session_init 을 실행하세요.",
    ):
        super().__init__(message)


class TistoryApiError(TistoryError):
    def __init__(self, message: str, status: int = 0, body: str = ""):
        super().__init__(message)
        self.status = status
        self.body = (body or "")[:300]


def looks_like_login_page(text: str) -> bool:
    head = text[:4096].lstrip()
    if head.startswith("{") or head.startswith("["):
        return False
    return any(m in head for m in LOGIN_MARKERS)


def validate_post_id(post_id: int | str) -> str:
    s = str(post_id).strip()
    if not _POST_ID_RE.match(s):
        raise TistoryApiError(f"post_id 는 양의 정수여야 합니다: {post_id!r}")
    return s


def validate_entry_url(host: str, entry_url: Any) -> str:
    """발행/수정 응답의 entryUrl 검증 후 마지막 path 세그먼트(post id 또는 page slug) 반환."""
    if not isinstance(entry_url, str) or not entry_url:
        raise TistoryApiError("응답에 entryUrl 이 없습니다 (세션 만료 또는 API 변경 가능성)")
    u = urlparse(entry_url)
    if (u.hostname or "").lower() != host:
        raise TistoryApiError(f"entryUrl 의 host 가 대상 블로그와 다릅니다: {entry_url}")
    path = u.path.rstrip("/")
    if re.fullmatch(r"/\d+", path):
        return path[1:]
    if re.fullmatch(r"/pages/[^/]+", path):
        return path.rsplit("/", 1)[1]
    raise TistoryApiError(f"entryUrl 형식을 해석할 수 없습니다: {entry_url}")


def default_post_body() -> dict[str, Any]:
    """Default body shared by POST/PUT. ``content`` must already be HTML."""
    return {
        "id": "0",
        "title": "",
        "content": "",
        "slogan": "",
        "visibility": 0,
        "category": 0,
        "tag": "",
        "published": 1,
        "password": "",
        "uselessMarginForEntry": 1,
        "cclCommercial": 0,
        "cclDerive": 0,
        "type": "post",
        "attachments": [],
        "recaptchaValue": "",
        "draftSequence": None,
        "totalWritingTimeMs": 0,
    }


def build_attachment_ref(upload: dict[str, Any]) -> str:
    """Upload response → attachment ref ``kage@{key}/{filename}?{query}`` (``&`` → ``&amp;``)."""
    query = urlparse(str(upload.get("url") or "")).query
    suffix = "?" + query.replace("&", "&amp;") if query else ""
    return f"kage@{upload['key']}/{upload['filename']}{suffix}"


def build_image_substitution(
    attachment_ref: str, width: int, height: int, style: str = "alignCenter"
) -> str:
    if style not in IMAGE_STYLES:
        raise ValueError(f"style 은 {IMAGE_STYLES} 중 하나여야 합니다: {style!r}")
    meta = json.dumps(
        {"originWidth": int(width), "originHeight": int(height), "style": style},
        separators=(",", ":"),
    )
    return f"[##_Image|{attachment_ref}|CDM|1.3|{meta}_##]"


class TistoryClient:
    """쿠키 헤더 하나로 관리자 API 를 호출한다. 브라우저 의존 없음."""

    def __init__(
        self,
        host: str,
        cookie_header: str,
        *,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ):
        self.host = host
        self._cookie_header = cookie_header
        self._http = httpx.Client(
            base_url=f"https://{host}",
            headers={
                "cookie": cookie_header,
                "origin": f"https://{host}",
                "referer": f"https://{host}/manage/",
                "user-agent": USER_AGENT,
            },
            follow_redirects=False,
            timeout=timeout,
            transport=transport,
        )

    @property
    def cookie_header(self) -> str:
        """공개 페이지 조회 등 별도 요청에 재사용할 쿠키 헤더(세션 저장소 재로드 방지)."""
        return self._cookie_header

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> TistoryClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ── 공통 ────────────────────────────────────────────────────────────
    def _request(
        self, method: str, path: str, *, accept: str = "application/json", **kwargs: Any
    ) -> httpx.Response:
        headers = dict(kwargs.pop("headers", None) or {})
        headers.setdefault("accept", accept)
        try:
            res = self._http.request(method, path, headers=headers, **kwargs)
        except httpx.HTTPError as exc:
            raise TistoryApiError(
                f"{method} {path} 네트워크 오류: {exc.__class__.__name__}"
            ) from exc
        if res.status_code == 401:
            raise SessionExpiredError()
        if 300 <= res.status_code < 400:
            loc = res.headers.get("location", "")
            if "/auth/login" in loc or "accounts.kakao.com" in loc:
                raise SessionExpiredError()
            raise TistoryApiError(f"{method} {path} 예상 밖 리다이렉트: {loc}", res.status_code)
        if res.status_code >= 400:
            raise TistoryApiError(
                f"{method} {path} → HTTP {res.status_code}", res.status_code, res.text
            )
        return res

    def _json(self, method: str, path: str, **kwargs: Any) -> Any:
        res = self._request(method, path, **kwargs)
        text = res.text
        if looks_like_login_page(text):
            raise SessionExpiredError()
        if not text.strip():
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise TistoryApiError(
                f"{method} {path} 응답이 JSON 이 아닙니다", res.status_code, text
            ) from exc

    def fetch_html(self, path: str) -> str:
        text = self._request("GET", path, accept="text/html").text
        if looks_like_login_page(text):
            raise SessionExpiredError()
        return text

    # ── 조회 ────────────────────────────────────────────────────────────
    def list_posts(
        self,
        *,
        category: int = -3,
        page: int = 1,
        keyword: str = "",
        search_type: str = "title",
        visibility: str = "all",
    ) -> dict[str, Any]:
        if visibility not in LIST_VISIBILITY_PARAM:
            raise ValueError(
                f"visibility 는 {tuple(LIST_VISIBILITY_PARAM)} 중 하나: {visibility!r}"
            )
        if search_type not in LIST_SEARCH_TYPES:
            raise ValueError(f"search_type 은 {LIST_SEARCH_TYPES} 중 하나: {search_type!r}")
        params = {
            "category": str(category),
            "page": str(page),
            "searchKeyword": keyword,
            "searchType": search_type,
            "visibility": LIST_VISIBILITY_PARAM[visibility],
        }
        data = self._json("GET", "/manage/posts.json", params=params)
        if not isinstance(data, dict):
            raise TistoryApiError("posts.json 응답 형식이 예상과 다릅니다", body=str(data))
        return data

    def find_post(self, post_id: int | str, *, max_pages: int = 20) -> dict[str, Any] | None:
        target = validate_post_id(post_id)
        for page in range(1, max_pages + 1):
            items = self.list_posts(page=page).get("items") or []
            for item in items:
                if str(item.get("id")) == target:
                    return item
            if not items:
                break
        return None

    def get_categories(self) -> dict[str, Any]:
        data = self._json("GET", "/manage/category.json")
        if not isinstance(data, dict):
            raise TistoryApiError("category.json 응답 형식이 예상과 다릅니다", body=str(data))
        return data

    # ── 글 CRUD ─────────────────────────────────────────────────────────
    def publish_post(self, fields: dict[str, Any]) -> dict[str, str]:
        """POST /manage/post.json — ALWAYS creates a new post (the server ignores any id).

        A failure after the request went out (timeout, odd response) may still have created the
        post, so the error tells the caller to check the list before retrying.
        """
        body = {**default_post_body(), **fields, "id": "0"}
        try:
            data = self._json("POST", "/manage/post.json", json=body)
            entry_url = data.get("entryUrl") if isinstance(data, dict) else None
            post_id = validate_entry_url(self.host, entry_url)
        except TistoryApiError as exc:
            raise TistoryApiError(
                f"{exc} — 글이 이미 생성됐을 수 있습니다. 재시도 전에 tistory_list_posts 로 "
                "확인하세요",
                exc.status,
                exc.body,
            ) from exc
        return {"entry_url": entry_url, "post_id": post_id}

    def update_post(self, post_id: int | str, fields: dict[str, Any]) -> dict[str, str]:
        """PUT /manage/post/{id}.json — full body; a missing content would blank the post."""
        pid = validate_post_id(post_id)
        body = {**default_post_body(), **fields, "id": pid}
        data = self._json("PUT", f"/manage/post/{pid}.json", json=body)
        entry_url = data.get("entryUrl") if isinstance(data, dict) else None
        validate_entry_url(self.host, entry_url)
        return {"entry_url": entry_url, "post_id": pid}

    def delete_post(self, post_id: int | str) -> dict[str, Any]:
        pid = validate_post_id(post_id)
        data = self._json("DELETE", f"/manage/post/{pid}.json")
        return data if isinstance(data, dict) else {"data": data}

    # ── 이미지 ──────────────────────────────────────────────────────────
    def upload_image(
        self, file_path: str, *, filename: str | None = None, mime: str | None = None
    ) -> dict[str, Any]:
        path = Path(file_path).expanduser()
        if not path.is_file():
            raise TistoryApiError(f"파일이 없습니다: {path}")
        ext = path.suffix.lower()
        if ext not in ALLOWED_IMAGE_MIMES:
            raise TistoryApiError(f"허용되지 않는 확장자 {ext!r} (png/jpg/jpeg/gif/webp)")
        size = path.stat().st_size
        if size > MAX_IMAGE_BYTES:
            raise TistoryApiError(f"파일이 너무 큽니다: {size} bytes (한도 {MAX_IMAGE_BYTES})")
        files = {
            "file": (filename or path.name, path.read_bytes(), mime or ALLOWED_IMAGE_MIMES[ext])
        }
        data = self._json("POST", "/manage/post/attach.json", files=files)
        if not isinstance(data, dict) or "key" not in data or "filename" not in data:
            raise TistoryApiError("attach.json 응답 형식이 예상과 다릅니다", body=str(data))
        return data

    # ── 자동저장 슬롯 ───────────────────────────────────────────────────
    def get_autosave(self) -> dict[str, Any] | None:
        """The autosave slot entry (response: ``{"autosavedEntry": {...} | null}``), or None."""
        data = self._json("GET", "/manage/autosave")
        if not isinstance(data, dict):
            return None
        entry = data.get("autosavedEntry", data)
        return entry if isinstance(entry, dict) and entry else None

    def save_autosave(
        self,
        *,
        title: str,
        content: str,
        tags: str = "",
        category_id: int = 0,
        attachments: list[str] | None = None,
    ) -> None:
        body: dict[str, Any] = {
            "title": title,
            "content": content,
            "tags": tags,
            "categoryId": int(category_id),
            "draftSequence": None,
            "totalWritingTimeMs": 0,
        }
        if attachments:
            body["attachments"] = list(attachments)
        self._json("POST", "/manage/autosave", json=body)
