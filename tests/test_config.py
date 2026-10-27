import pytest

from tistory_mcp.config import InvalidHostError, normalize_host, settings, validate_cdp_url


def test_normalize_host_variants():
    assert normalize_host("https://MyBlog.tistory.com/manage/") == "myblog.tistory.com"
    assert normalize_host("myblog.tistory.com") == "myblog.tistory.com"
    assert normalize_host(" myblog.tistory.com/92 ") == "myblog.tistory.com"


def test_normalize_host_rejects_non_tistory_by_default(monkeypatch):
    with pytest.raises(InvalidHostError):
        normalize_host("example.com")
    monkeypatch.setenv("TISTORY_MCP_ALLOW_ANY_HOST", "1")
    assert normalize_host("example.com") == "example.com"


@pytest.mark.parametrize("bad", ["", "   ", "http://", "bad host.tistory.com", "-x.tistory.com"])
def test_normalize_host_rejects_garbage(bad):
    with pytest.raises(InvalidHostError):
        normalize_host(bad)


def test_cdp_url_loopback_only(monkeypatch):
    assert validate_cdp_url("http://127.0.0.1:9222") == "http://127.0.0.1:9222"
    with pytest.raises(InvalidHostError):
        validate_cdp_url("http://10.0.0.5:9222")
    monkeypatch.setenv("TISTORY_MCP_ALLOW_REMOTE_CDP", "1")
    assert validate_cdp_url("http://10.0.0.5:9222")


def test_settings_defaults_and_env(monkeypatch):
    s = settings()
    assert s.min_interval_sec == 60 and s.daily_cap == 20 and s.session_store == "file"
    monkeypatch.setenv("TISTORY_MCP_MIN_INTERVAL_SEC", "5")
    monkeypatch.setenv("TISTORY_MCP_DAILY_CAP", "abc")
    monkeypatch.setenv("TISTORY_MCP_SESSION_STORE", "weird")
    s = settings()
    assert s.min_interval_sec == 5 and s.daily_cap == 20 and s.session_store == "file"
