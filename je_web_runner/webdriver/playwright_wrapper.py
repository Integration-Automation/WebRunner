"""
Playwright 同步 backend 包裝器（MVP），與既有 Selenium 路徑並行存在。
Playwright sync backend wrapper (MVP) running side-by-side with the existing
Selenium path; selection happens at action time via the WR_pw_* commands.

設計原則 / Design notes:
- ``playwright`` 為軟相依，未安裝時呼叫才會丟出含安裝提示的錯誤。
  Playwright is a soft dependency; missing-import is reported only on first use.
- 不改寫 ``WebDriverWrapper`` 也不重做 element wrapper；本檔只暴露 MVP 操作
  （launch / navigate / find / click / fill / screenshot / quit），讓使用者
  可以漸進採用，避免一次大改的回歸風險。
  Does not touch WebDriverWrapper or the element wrapper; only exposes MVP
  operations so adoption can be incremental and the regression surface stays
  small.
"""
from __future__ import annotations

from typing import Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class PlaywrightBackendError(WebRunnerException):
    """Raised when the Playwright backend is misused or unavailable."""


def _require_playwright():
    """Import Playwright lazily; surface a clear install hint when missing."""
    try:
        from playwright.sync_api import sync_playwright  # type: ignore[import-not-found]
        return sync_playwright
    except ImportError as error:
        raise PlaywrightBackendError(
            "Playwright is not installed. Install with: "
            "pip install playwright && python -m playwright install"
        ) from error


_SUPPORTED_BROWSERS = frozenset({"chromium", "firefox", "webkit"})


class PlaywrightWrapper:
    """
    Playwright 同步 API 的最小包裝。一個實例對應一個 browser+page。
    Minimal sync-API wrapper. One instance owns one browser and one page.
    """

    def __init__(self) -> None:
        self._playwright = None
        self._browser = None
        self._page = None

    @property
    def page(self):
        if self._page is None:
            raise PlaywrightBackendError("Playwright page not launched; call launch() first")
        return self._page

    def launch(self, browser: str = "chromium", headless: bool = True) -> None:
        """
        啟動指定瀏覽器並開新分頁
        Launch the requested browser and open a fresh page.

        :param browser: chromium / firefox / webkit
        :param headless: 是否無頭模式 / run headless
        """
        web_runner_logger.info(f"playwright launch: browser={browser}, headless={headless}")
        if browser not in _SUPPORTED_BROWSERS:
            raise PlaywrightBackendError(
                f"unsupported playwright browser: {browser!r}; "
                f"choose one of {sorted(_SUPPORTED_BROWSERS)}"
            )
        sync_playwright = _require_playwright()
        self._playwright = sync_playwright().start()
        browser_type = getattr(self._playwright, browser)
        self._browser = browser_type.launch(headless=headless)
        self._page = self._browser.new_page()

    def to_url(self, url: str) -> None:
        """Navigate the active page."""
        web_runner_logger.info(f"playwright to_url: {url}")
        self.page.goto(url)

    def find_element(self, selector: str):
        """Return the first element matching the Playwright selector, or None."""
        web_runner_logger.info(f"playwright find_element: {selector}")
        return self.page.query_selector(selector)

    def click(self, selector: str) -> None:
        """Click the first element matching the selector."""
        web_runner_logger.info(f"playwright click: {selector}")
        self.page.click(selector)

    def fill(self, selector: str, value: str) -> None:
        """Fill the first matching input with ``value``."""
        web_runner_logger.info(f"playwright fill: {selector}")
        self.page.fill(selector, value)

    def screenshot(self, path: str, full_page: bool = False) -> str:
        """Save a PNG screenshot to ``path`` and return the path."""
        web_runner_logger.info(f"playwright screenshot: {path}")
        self.page.screenshot(path=path, full_page=full_page)
        return path

    def quit(self) -> None:
        """Close the browser and stop the Playwright runtime."""
        web_runner_logger.info("playwright quit")
        try:
            if self._browser is not None:
                self._browser.close()
        finally:
            self._browser = None
            self._page = None
            if self._playwright is not None:
                self._playwright.stop()
            self._playwright = None


playwright_wrapper_instance = PlaywrightWrapper()


def pw_launch(browser: str = "chromium", headless: bool = True) -> None:
    playwright_wrapper_instance.launch(browser=browser, headless=headless)


def pw_to_url(url: str) -> None:
    playwright_wrapper_instance.to_url(url)


def pw_click(selector: str) -> None:
    playwright_wrapper_instance.click(selector)


def pw_fill(selector: str, value: str) -> None:
    playwright_wrapper_instance.fill(selector, value)


def pw_screenshot(path: str, full_page: bool = False) -> str:
    return playwright_wrapper_instance.screenshot(path, full_page=full_page)


def pw_quit() -> None:
    playwright_wrapper_instance.quit()


def pw_find_element(selector: str) -> Optional[object]:
    return playwright_wrapper_instance.find_element(selector)
