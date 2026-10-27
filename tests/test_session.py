import stat
import sys
import time

import pytest

from tistory_mcp.config import settings
from tistory_mcp.session import (
    SessionStore,
    StoredSession,
    cookie_header,
    earliest_expiry,
    filter_cookies_for_host,
)

HOST = "example.tistory.com"


def _c(name, value, domain, expires=-1):
    return {"name": name, "value": value, "domain": domain, "path": "/", "expires": expires}


def test_cookie_header_filters_domain_expiry_and_dedups():
    now = time.time()
    cookies = [
        _c("TSSESSION", "s1", ".tistory.com"),
        _c("TSSESSION", "s2", "example.tistory.com"),  # host 에 더 가까운 도메인 우선
        _c("OLD", "x", ".tistory.com", expires=now - 10),  # 만료
        _c("KAKAO", "k", ".kakao.com"),  # 다른 도메인
        _c("PERM", "p", ".tistory.com", expires=now + 3600),
    ]
    header = cookie_header(cookies, HOST, now=now)
    assert header == "TSSESSION=s2; PERM=p"
    # 이미 지난 OLD(now-10) 가 아니라, 살아있는 PERM 기준으로 보고해야 한다
    assert earliest_expiry(cookies, HOST, now=now) == now + 3600
    assert [c["name"] for c in filter_cookies_for_host(cookies, HOST)] == [
        "TSSESSION",
        "TSSESSION",
        "OLD",
        "PERM",
    ]


def test_store_roundtrip_with_0600_permissions():
    store = SessionStore(settings())
    sess = StoredSession(host=HOST, cookies=[_c("TSSESSION", "v", ".tistory.com")], saved_at=1.0)
    location = store.save(sess)
    path = store.path_for(HOST)
    assert location == str(path)
    if sys.platform != "win32":
        # Windows 는 POSIX 모드 비트가 없다 (사용자 프로필 ACL 이 대신 보호한다)
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    loaded = store.load(HOST)
    assert loaded is not None and loaded.cookies[0]["value"] == "v" and loaded.host == HOST
    assert store.delete(HOST) is True
    assert store.load(HOST) is None
    assert store.delete(HOST) is False


def test_earliest_expiry_ignores_already_expired_cookies():
    now = time.time()
    only_dead = [_c("DEAD", "x", ".tistory.com", expires=now - 86400)]
    assert earliest_expiry(only_dead, HOST, now=now) is None
    # 세션 쿠키(-1)만 있으면 만료 시각을 알 수 없다
    assert earliest_expiry([_c("S", "v", ".tistory.com")], HOST, now=now) is None


def test_keyring_backend_missing_package_gives_hint(monkeypatch):
    import sys

    from tistory_mcp.session import SessionStoreError

    monkeypatch.setenv("TISTORY_MCP_SESSION_STORE", "keyring")
    monkeypatch.setitem(sys.modules, "keyring", None)  # makes `import keyring` fail
    with pytest.raises(SessionStoreError, match="keyring"):
        SessionStore(settings()).load(HOST)
