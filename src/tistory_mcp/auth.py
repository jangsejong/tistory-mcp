"""One-time headed browser login. Kakao OAuth and the KakaoTalk push approval are done by a human.

Two paths:
  A. Playwright opens a visible browser — the bundled Chromium, or an installed Chrome/Edge.
  B. ``cdp_url`` attaches to a browser already running with ``--remote-debugging-port``
     (for shells without a display: WSL, SSH, containers).
Login is complete once the page settles on ``{host}/manage*``. Only the blog's own cookies are
kept; the browser is closed (path A) or just the tab (path B).
"""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import urlparse

from .session import StoredSession, filter_cookies_for_host

# Bundled Chromium first (what `tistory-mcp install-browser` provides), then the browsers most
# desktops already have, so the 300MB download is usually unnecessary.
BROWSER_CHANNELS: tuple[str | None, ...] = (None, "chrome", "msedge")
INSTALL_HINT = "`tistory-mcp install-browser` 로 Chromium 을 설치하거나 Chrome/Edge 를 설치하세요"


class LoginError(Exception):
    pass


def is_manage_url(url: str, host: str) -> bool:
    u = urlparse(url)
    return (u.hostname or "").lower() == host and u.path.startswith("/manage")


async def launch_browser(chromium: Any, error_cls: type[BaseException]) -> Any:
    """Try each channel in BROWSER_CHANNELS; raise LoginError listing why each one failed."""
    failures: list[str] = []
    for channel in BROWSER_CHANNELS:
        try:
            if channel is None:
                return await chromium.launch(headless=False)
            return await chromium.launch(headless=False, channel=channel)
        except error_cls as exc:
            first = str(exc).splitlines()[0] if str(exc) else exc.__class__.__name__
            failures.append(f"{channel or 'chromium'}: {first}")
    raise LoginError(f"브라우저를 열지 못했습니다. {INSTALL_HINT} ({' / '.join(failures)})")


async def login_interactive(
    host: str, *, timeout_sec: int = 300, cdp_url: str | None = None
) -> StoredSession:
    try:
        from playwright.async_api import Error as PlaywrightError
        from playwright.async_api import TimeoutError as PlaywrightTimeout
        from playwright.async_api import async_playwright
    except ImportError as exc:  # pragma: no cover
        raise LoginError("playwright 가 설치되지 않았습니다: pip install playwright") from exc

    async with async_playwright() as p:
        browser = None
        try:
            if cdp_url:
                browser = await p.chromium.connect_over_cdp(cdp_url)
                context = browser.contexts[0] if browser.contexts else await browser.new_context()
            else:
                browser = await launch_browser(p.chromium, PlaywrightError)
                context = await browser.new_context()
            page = await context.new_page()
            await page.goto(f"https://{host}/manage", wait_until="domcontentloaded")
            await page.wait_for_url(lambda u: is_manage_url(u, host), timeout=timeout_sec * 1000)
            await page.wait_for_load_state("domcontentloaded")
            cookies = [dict(c) for c in await context.cookies()]
            if cdp_url:
                await page.close()
        except PlaywrightTimeout as exc:
            raise LoginError(
                f"{timeout_sec}초 안에 로그인이 완료되지 않았습니다. 브라우저 창이 보이지 않는 "
                "환경(WSL·SSH·컨테이너)이면 cdp_url 경로를 사용하세요."
            ) from exc
        except PlaywrightError as exc:
            msg = str(exc).splitlines()[0] if str(exc) else exc.__class__.__name__
            hint = f" ({INSTALL_HINT})" if "Executable doesn't exist" in str(exc) else ""
            raise LoginError(f"브라우저 오류: {msg}{hint}") from exc
        finally:
            if browser is not None and not cdp_url:
                await browser.close()

    kept = filter_cookies_for_host(cookies, host)
    if not kept:
        raise LoginError("로그인은 끝났지만 블로그 도메인 쿠키를 찾지 못했습니다")
    return StoredSession(
        host=host, cookies=kept, saved_at=time.time(), source="cdp" if cdp_url else "playwright"
    )
