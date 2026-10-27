"""Login session (cookie) store. Default = 0600 file, optional = OS keyring.

The cookies grant full management rights on the blog. Values are never written to logs,
tool responses or exception messages.
"""

from __future__ import annotations

import json
import os
import stat
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from .config import Settings, settings

KEYRING_SERVICE = "tistory-mcp"
KEYRING_HINT = (
    'keyring 백엔드를 쓰려면 `pip install "tistory-mcp[keyring]"` 와 OS 자격증명 저장소'
    "(macOS Keychain / Linux Secret Service)가 필요합니다. 파일 저장소로 돌아가려면 "
    "TISTORY_MCP_SESSION_STORE 를 비우세요"
)


class SessionStoreError(ValueError):
    """The configured session backend is unavailable (keyring missing or not usable)."""


def _keyring():
    try:
        import keyring
        import keyring.errors
    except ImportError as exc:
        raise SessionStoreError(f"keyring 패키지가 없습니다. {KEYRING_HINT}") from exc
    return keyring


@dataclass
class StoredSession:
    host: str
    cookies: list[dict]
    saved_at: float
    source: str = "playwright"

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, text: str) -> StoredSession:
        data = json.loads(text)
        return cls(
            host=str(data["host"]),
            cookies=list(data.get("cookies") or []),
            saved_at=float(data.get("saved_at") or 0),
            source=str(data.get("source") or "playwright"),
        )


def cookie_domain_matches(cookie_domain: str, host: str) -> bool:
    d = (cookie_domain or "").lower().lstrip(".")
    if not d:
        return False
    return host == d or host.endswith("." + d)


def _expires_of(cookie: dict) -> float | None:
    exp = cookie.get("expires")
    if isinstance(exp, bool) or not isinstance(exp, int | float):
        return None
    return float(exp)


def cookie_header(cookies: list[dict], host: str, *, now: float | None = None) -> str:
    """host 에 해당하는 미만료 쿠키를 `name=value; ...` 로 직렬화.

    같은 이름이 여러 도메인에 있으면 host 에 더 가까운(긴) 도메인을 우선한다.
    """
    now = time.time() if now is None else now
    matched = []
    for c in cookies:
        exp = _expires_of(c)
        if exp is not None and 0 < exp < now:
            continue
        if cookie_domain_matches(str(c.get("domain", "")), host):
            matched.append(c)
    matched.sort(key=lambda c: len(str(c.get("domain", ""))), reverse=True)
    seen: set[str] = set()
    parts: list[str] = []
    for c in matched:
        name = c.get("name")
        if not name or name in seen:
            continue
        seen.add(name)
        parts.append(f"{name}={c.get('value', '')}")
    return "; ".join(parts)


def earliest_expiry(cookies: list[dict], host: str, *, now: float | None = None) -> float | None:
    """지금 유효한 쿠키 중 가장 먼저 만료되는 시각.

    이미 지난 만료값은 제외한다 — `cookie_header` 가 어차피 버리는 쿠키라, 포함하면
    세션이 살아 있는데도 "만료일이 과거"로 보고돼 오해를 부른다.
    """
    now = time.time() if now is None else now
    vals = []
    for c in cookies:
        exp = _expires_of(c)
        if exp is None or exp <= now:
            continue
        if cookie_domain_matches(str(c.get("domain", "")), host):
            vals.append(exp)
    return min(vals) if vals else None


def filter_cookies_for_host(cookies: list[dict], host: str) -> list[dict]:
    return [c for c in cookies if cookie_domain_matches(str(c.get("domain", "")), host)]


class SessionStore:
    def __init__(self, cfg: Settings | None = None):
        self._cfg = cfg or settings()

    @property
    def backend(self) -> str:
        return self._cfg.session_store

    def path_for(self, host: str) -> Path:
        return self._cfg.sessions_dir / f"{host}.json"

    def save(self, session: StoredSession) -> str:
        """저장 후 위치 설명 문자열을 돌려준다(쿠키 값은 포함하지 않음)."""
        if self.backend == "keyring":
            keyring = _keyring()
            try:
                keyring.set_password(KEYRING_SERVICE, session.host, session.to_json())
            except keyring.errors.KeyringError as exc:
                raise SessionStoreError(f"keyring 저장 실패: {exc}. {KEYRING_HINT}") from exc
            return f"keyring:{KEYRING_SERVICE}/{session.host}"
        path = self.path_for(session.host)
        path.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(path.parent, 0o700)
        tmp = path.with_name(path.name + ".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(session.to_json())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
        return str(path)

    def load(self, host: str) -> StoredSession | None:
        if self.backend == "keyring":
            keyring = _keyring()
            try:
                text = keyring.get_password(KEYRING_SERVICE, host)
            except keyring.errors.KeyringError as exc:
                raise SessionStoreError(f"keyring 조회 실패: {exc}. {KEYRING_HINT}") from exc
            return StoredSession.from_json(text) if text else None
        path = self.path_for(host)
        if not path.is_file():
            return None
        if stat.S_IMODE(path.stat().st_mode) & 0o077:
            os.chmod(path, 0o600)
        return StoredSession.from_json(path.read_text(encoding="utf-8"))

    def delete(self, host: str) -> bool:
        if self.backend == "keyring":
            keyring = _keyring()
            try:
                keyring.delete_password(KEYRING_SERVICE, host)
                return True
            except keyring.errors.PasswordDeleteError:
                return False
            except keyring.errors.KeyringError as exc:
                raise SessionStoreError(f"keyring 삭제 실패: {exc}. {KEYRING_HINT}") from exc
        path = self.path_for(host)
        if path.is_file():
            path.unlink()
            return True
        return False
