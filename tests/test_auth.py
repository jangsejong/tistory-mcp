import pytest

from tistory_mcp.auth import BROWSER_CHANNELS, LoginError, is_manage_url, launch_browser


class FakeError(Exception):
    pass


class FakeChromium:
    def __init__(self, ok_channel):
        self.ok_channel = ok_channel
        self.calls = []

    async def launch(self, **kw):
        channel = kw.get("channel")
        self.calls.append(channel)
        if channel != self.ok_channel:
            raise FakeError("Executable doesn't exist at /x\nrun playwright install")
        return f"browser:{channel}"


@pytest.mark.anyio
async def test_launch_browser_falls_back_through_channels():
    chromium = FakeChromium(ok_channel="msedge")
    assert await launch_browser(chromium, FakeError) == "browser:msedge"
    assert chromium.calls == list(BROWSER_CHANNELS)


@pytest.mark.anyio
async def test_launch_browser_reports_every_failure():
    chromium = FakeChromium(ok_channel="nothing")
    with pytest.raises(LoginError, match="install-browser") as ei:
        await launch_browser(chromium, FakeError)
    assert "chromium:" in str(ei.value) and "msedge:" in str(ei.value)
    assert "\n" not in str(ei.value)  # only the first line of each error is kept


def test_is_manage_url():
    assert is_manage_url("https://myblog.tistory.com/manage/posts", "myblog.tistory.com")
    assert not is_manage_url("https://www.tistory.com/auth/login", "myblog.tistory.com")
