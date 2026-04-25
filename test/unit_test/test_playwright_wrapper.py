import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from je_web_runner.webdriver import playwright_wrapper as pw_module
from je_web_runner.webdriver.playwright_wrapper import (
    PlaywrightBackendError,
    PlaywrightWrapper,
)


class _FakePage:
    def __init__(self):
        self.calls = []
        self.query_target = SimpleNamespace(tag="found")

    def goto(self, url):
        self.calls.append(("goto", url))

    def query_selector(self, selector):
        self.calls.append(("query_selector", selector))
        return self.query_target

    def click(self, selector):
        self.calls.append(("click", selector))

    def fill(self, selector, value):
        self.calls.append(("fill", selector, value))

    def screenshot(self, path, full_page=False):
        self.calls.append(("screenshot", path, full_page))


class _FakeBrowser:
    def __init__(self, page):
        self._page = page
        self.closed = False

    def new_page(self):
        return self._page

    def close(self):
        self.closed = True


class _FakeBrowserType:
    def __init__(self, browser):
        self._browser = browser
        self.launch_called_with = None

    def launch(self, headless=True):
        self.launch_called_with = headless
        return self._browser


class _FakePlaywright:
    def __init__(self, page):
        self.chromium = _FakeBrowserType(_FakeBrowser(page))
        self.firefox = _FakeBrowserType(_FakeBrowser(page))
        self.webkit = _FakeBrowserType(_FakeBrowser(page))
        self.stopped = False

    def stop(self):
        self.stopped = True


class _FakeSyncPlaywright:
    def __init__(self, page):
        self._page = page
        self.started = False

    def start(self):
        self.started = True
        return _FakePlaywright(self._page)

    def __call__(self):
        return self


class TestPlaywrightWrapper(unittest.TestCase):

    def _make_wrapper(self):
        page = _FakePage()
        sync_factory = _FakeSyncPlaywright(page)
        with patch.object(pw_module, "_require_playwright", return_value=sync_factory):
            wrapper = PlaywrightWrapper()
            wrapper.launch(browser="chromium", headless=True)
        return wrapper, page

    def test_page_property_raises_before_launch(self):
        wrapper = PlaywrightWrapper()
        with self.assertRaises(PlaywrightBackendError):
            _ = wrapper.page

    def test_unsupported_browser_rejected(self):
        wrapper = PlaywrightWrapper()
        with self.assertRaises(PlaywrightBackendError):
            wrapper.launch(browser="ie")

    def test_launch_navigate_click_fill_screenshot_quit(self):
        wrapper, page = self._make_wrapper()
        wrapper.to_url("https://example.com")
        wrapper.click("#submit")
        wrapper.fill("#input", "hello")
        wrapper.screenshot("out.png", full_page=True)
        wrapper.quit()
        self.assertIn(("goto", "https://example.com"), page.calls)
        self.assertIn(("click", "#submit"), page.calls)
        self.assertIn(("fill", "#input", "hello"), page.calls)
        self.assertIn(("screenshot", "out.png", True), page.calls)
        self.assertIsNone(wrapper._browser)
        self.assertIsNone(wrapper._page)

    def test_find_element_returns_query_result(self):
        wrapper, page = self._make_wrapper()
        result = wrapper.find_element("#anchor")
        self.assertIs(result, page.query_target)

    def test_missing_playwright_raises_helpful_error(self):
        with patch.dict(sys.modules, {"playwright": None, "playwright.sync_api": None}):
            wrapper = PlaywrightWrapper()
            with self.assertRaises(PlaywrightBackendError) as context:
                wrapper.launch()
            self.assertIn("pip install playwright", str(context.exception))


if __name__ == "__main__":
    unittest.main()
