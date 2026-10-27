import pytest


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """세션·rate limit 상태를 실제 ~/.config 에 남기지 않는다."""
    monkeypatch.setenv("TISTORY_MCP_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("TISTORY_MCP_SESSION_STORE", raising=False)
    monkeypatch.delenv("TISTORY_MCP_ALLOW_ANY_HOST", raising=False)
    monkeypatch.delenv("TISTORY_MCP_CDP_URL", raising=False)
    return tmp_path


@pytest.fixture
def anyio_backend():
    return "asyncio"
