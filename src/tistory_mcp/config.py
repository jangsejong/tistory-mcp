"""설정·경로·호스트 정규화. 환경변수는 호출 시점에 읽는다(테스트 격리·재시작 없이 반영)."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

APP_NAME = "tistory-mcp"
_HOST_RE = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$")
_LOOPBACK = {"localhost", "127.0.0.1", "::1"}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    home: Path
    session_store: str
    min_interval_sec: int
    daily_cap: int
    allow_any_host: bool
    allow_remote_cdp: bool
    cdp_url: str | None
    log_level: str

    @property
    def sessions_dir(self) -> Path:
        return self.home / "sessions"

    @property
    def ratelimit_path(self) -> Path:
        return self.home / "ratelimit.json"


def settings() -> Settings:
    home_env = os.environ.get("TISTORY_MCP_HOME")
    if home_env:
        home = Path(home_env).expanduser()
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        base = Path(xdg).expanduser() if xdg else Path.home() / ".config"
        home = base / APP_NAME
    store = (os.environ.get("TISTORY_MCP_SESSION_STORE") or "file").strip().lower()
    if store not in ("file", "keyring"):
        store = "file"
    return Settings(
        home=home,
        session_store=store,
        min_interval_sec=_env_int("TISTORY_MCP_MIN_INTERVAL_SEC", 60),
        daily_cap=_env_int("TISTORY_MCP_DAILY_CAP", 20),
        allow_any_host=os.environ.get("TISTORY_MCP_ALLOW_ANY_HOST") == "1",
        allow_remote_cdp=os.environ.get("TISTORY_MCP_ALLOW_REMOTE_CDP") == "1",
        cdp_url=os.environ.get("TISTORY_MCP_CDP_URL") or None,
        log_level=os.environ.get("TISTORY_MCP_LOG_LEVEL") or "INFO",
    )


class InvalidHostError(ValueError):
    """blog_url 이 비었거나 형식이 틀리거나 허용 도메인이 아닐 때."""


def normalize_host(blog_url: str, *, allow_any_host: bool | None = None) -> str:
    """`https://x.tistory.com/path` / `x.tistory.com` → `x.tistory.com`.

    기본은 `*.tistory.com` 만 허용한다(SSRF·오발행 방지). 커스텀 도메인은
    `TISTORY_MCP_ALLOW_ANY_HOST=1` 로 열 수 있다.
    """
    raw = (blog_url or "").strip()
    if not raw:
        raise InvalidHostError("blog_url 이 비어 있습니다. 예: myblog.tistory.com")
    host = (urlparse(raw).hostname or "") if "://" in raw else raw.split("/", 1)[0]
    host = host.strip().lower().rstrip(".")
    if not _HOST_RE.match(host):
        raise InvalidHostError(f"blog_url 형식이 올바르지 않습니다: {raw!r}")
    if allow_any_host is None:
        allow_any_host = settings().allow_any_host
    if not allow_any_host and not host.endswith(".tistory.com"):
        raise InvalidHostError(
            f"{host} 은(는) *.tistory.com 이 아닙니다. "
            "커스텀 도메인은 TISTORY_MCP_ALLOW_ANY_HOST=1 로 허용하세요."
        )
    return host


def validate_cdp_url(cdp_url: str, *, allow_remote: bool | None = None) -> str:
    """CDP 엔드포인트는 기본 loopback 만 허용한다(원격 브라우저에 쿠키가 남지 않게)."""
    u = urlparse(cdp_url.strip())
    if u.scheme not in ("http", "https", "ws", "wss") or not u.hostname:
        raise InvalidHostError(f"cdp_url 형식이 올바르지 않습니다: {cdp_url!r}")
    if allow_remote is None:
        allow_remote = settings().allow_remote_cdp
    if not allow_remote and u.hostname not in _LOOPBACK:
        raise InvalidHostError(
            "cdp_url 은 기본적으로 localhost/127.0.0.1 만 허용합니다 "
            "(원격 허용: TISTORY_MCP_ALLOW_REMOTE_CDP=1)."
        )
    return cdp_url.strip()
