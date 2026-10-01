"""
非同步 Playwright 工作階段 / One browser for many concurrent action lists, one context each.

:class:`AsyncBrowserPool` starts ``playwright.async_api`` and a browser once; every action
list run by :class:`~je_web_runner.utils.async_executor.executor.AsyncExecutor` gets its
own :class:`AsyncSession`: a fresh browser context (its own cookies and storage, like a
separate user) with its pages and the WebSocket frames they received. Playwright is
imported only when a pool starts.
"""
from __future__ import annotations

import asyncio
from typing import Any

from je_web_runner.utils.exception.exceptions import WebRunnerException

_BROWSERS = ("chromium", "firefox", "webkit")


class AsyncSessionError(WebRunnerException):
    """No page to act on, an unknown page or browser, or Playwright is not installed."""


class AsyncSession:
    """One action list's browser context, its pages (the current one first in line) and WebSocket frames."""

    def __init__(self, context: Any) -> None:
        self.context = context
        self.pages: list[Any] = []
        self.current = -1
        self.websocket_frames: list[dict[str, Any]] = []

    @property
    def page(self) -> Any:
        """The current page; raises when none is open."""
        if not self.pages:
            raise AsyncSessionError("no page is open in this session; WR_apw_goto or WR_apw_new_page opens one")
        return self.pages[self.current]

    async def new_page(self) -> Any:
        """Open a page, record its WebSocket frames, and make it current."""
        page = await self.context.new_page()
        page.on("websocket", self._watch_websocket)
        self.pages.append(page)
        self.current = len(self.pages) - 1
        return page

    def switch_to(self, index: int) -> Any:
        """Make page ``index`` current."""
        if not 0 <= int(index) < len(self.pages):
            raise AsyncSessionError(f"no page {index}; {len(self.pages)} open")
        self.current = int(index)
        return self.page

    async def close_page(self) -> None:
        """Close the current page; the previous one becomes current."""
        page = self.page
        await page.close()
        self.pages.pop(self.current)
        self.current = len(self.pages) - 1

    def _watch_websocket(self, websocket: Any) -> None:
        url = websocket.url

        def record(direction: str):
            return lambda payload: self.websocket_frames.append(
                {"url": url, "direction": direction, "payload": payload})
        websocket.on("framereceived", record("received"))
        websocket.on("framesent", record("sent"))

    async def close(self) -> None:
        """Close the context and every page in it."""
        await self.context.close()
        self.pages, self.current = [], -1


class AsyncBrowserPool:
    """Starts Playwright and one browser on first use; hands out one context per session."""

    def __init__(self, browser: str = "chromium", headless: bool = True, **launch_options: Any) -> None:
        if browser not in _BROWSERS:
            raise AsyncSessionError(f"browser must be one of {list(_BROWSERS)}, got {browser!r}")
        self.browser_name = browser
        self.headless = headless
        self.launch_options = launch_options
        self._playwright: Any = None
        self._browser: Any = None
        self._lock = asyncio.Lock()

    async def _ensure_browser(self) -> Any:
        async with self._lock:  # concurrent action lists must not each launch a browser
            if self._browser is None:
                try:
                    from playwright.async_api import async_playwright
                except ImportError as error:
                    raise AsyncSessionError(
                        "Playwright is not installed: pip install playwright && python -m playwright install"
                    ) from error
                self._playwright = await async_playwright().start()
                self._browser = await getattr(self._playwright, self.browser_name).launch(
                    headless=self.headless, **self.launch_options)
        return self._browser

    async def open_session(self, **context_options: Any) -> AsyncSession:
        """A new session in a fresh browser context (``context_options`` go to ``new_context``)."""
        browser = await self._ensure_browser()
        return AsyncSession(await browser.new_context(**context_options))

    async def close(self) -> None:
        """Close the browser and stop Playwright."""
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None
