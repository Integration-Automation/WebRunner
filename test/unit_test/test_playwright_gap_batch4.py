"""Playwright connect / persistent context / downloads / cache (progress #19, fourth batch)."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from je_web_runner.utils.executor.action_executor import executor
from je_web_runner.webdriver import playwright_wrapper as pw_module
from je_web_runner.webdriver.playwright_wrapper import PlaywrightBackendError, PlaywrightWrapper


def _runtime():
    playwright = MagicMock()
    factory = MagicMock()
    factory.start.return_value = playwright
    return playwright, patch.object(pw_module, "_require_playwright", return_value=MagicMock(return_value=factory))


class TestConnect(unittest.TestCase):

    def test_connect_to_a_playwright_server(self):
        playwright, runtime = _runtime()
        browser = playwright.firefox.connect.return_value
        with runtime:
            wrapper = PlaywrightWrapper()
            wrapper.connect("ws://grid:3000/", browser="firefox", context_options={"locale": "en-GB"})
        playwright.firefox.connect.assert_called_once_with("ws://grid:3000/")
        browser.new_context.assert_called_once_with(locale="en-GB")
        self.assertIs(wrapper.page, browser.new_context.return_value.new_page.return_value)

    def test_connect_over_cdp_adopts_the_open_context_and_its_pages(self):
        playwright, runtime = _runtime()
        browser = playwright.chromium.connect_over_cdp.return_value
        existing = MagicMock()
        first, second = MagicMock(), MagicMock()
        existing.pages = [first, second]
        browser.contexts = [existing]
        with runtime:
            wrapper = PlaywrightWrapper()
            wrapper.connect_over_cdp("http://localhost:9222")
        self.assertIs(wrapper.context, existing)
        self.assertEqual(wrapper.page_count(), 2)
        browser.new_context.assert_not_called()
        with self.assertRaises(PlaywrightBackendError):
            wrapper.set_timezone("UTC")  # would close the user's own context

    def test_quit_after_attaching_disconnects_without_closing_the_users_context(self):
        # Browser.close() on a CDP-connected browser only disconnects (Playwright docs).
        playwright, runtime = _runtime()
        browser = playwright.chromium.connect_over_cdp.return_value
        users_context = MagicMock(pages=[MagicMock()])
        browser.contexts = [users_context]
        with runtime:
            wrapper = PlaywrightWrapper()
            wrapper.connect_over_cdp("http://localhost:9222")
            wrapper.quit()
        browser.close.assert_called_once_with()
        users_context.close.assert_not_called()
        playwright.stop.assert_called_once_with()


class TestPersistentContext(unittest.TestCase):

    def test_extensions_become_chromium_args(self):
        playwright, runtime = _runtime()
        context = playwright.chromium.launch_persistent_context.return_value
        context.pages = []
        context.browser = None  # Playwright returns no browser object for a persistent context
        with runtime:
            wrapper = PlaywrightWrapper()
            wrapper.launch_persistent("profile", extension_paths=["ext/a", "ext/b"], locale="fr-FR")
        kwargs = playwright.chromium.launch_persistent_context.call_args.kwargs
        self.assertEqual(playwright.chromium.launch_persistent_context.call_args.args, ("profile",))
        self.assertIn("--load-extension=ext/a,ext/b", kwargs["args"])
        self.assertIn("--disable-extensions-except=ext/a,ext/b", kwargs["args"])
        self.assertEqual(kwargs["locale"], "fr-FR")
        self.assertIs(wrapper.page, context.new_page.return_value)
        wrapper.quit()
        context.close.assert_called_once_with()


def _launched():
    playwright, runtime = _runtime()
    page = MagicMock()
    page.url = "about:blank"
    context = playwright.chromium.launch.return_value.new_context.return_value
    context.new_page.return_value = page
    with runtime:
        wrapper = PlaywrightWrapper()
        wrapper.launch()
    return wrapper, context, page


class TestDownloadAndCache(unittest.TestCase):

    def test_download_into_a_directory_keeps_the_suggested_name(self):
        wrapper, _context, page = _launched()
        download = page.expect_download.return_value.__enter__.return_value.value
        download.suggested_filename = "report.csv"
        with tempfile.TemporaryDirectory() as tmp:
            saved = wrapper.download("#export", tmp)
            self.assertEqual(Path(saved), Path(tmp) / "report.csv")
        page.click.assert_called_once_with("#export")
        download.save_as.assert_called_once_with(saved)

    def test_cache_off_routes_everything_through_fallback_and_back_on_removes_it(self):
        wrapper, context, _page = _launched()
        wrapper.set_cache_disabled(True)
        pattern, handler = context.route.call_args.args
        self.assertEqual(pattern, "**/*")
        route = MagicMock()
        handler(route)
        route.fallback.assert_called_once_with()
        wrapper.set_cache_disabled(False)
        context.unroute.assert_called_once_with("**/*", handler)


class TestCommands(unittest.TestCase):

    def test_commands_are_registered(self):
        for name in ("WR_pw_connect", "WR_pw_connect_over_cdp", "WR_pw_launch_persistent", "WR_pw_download",
                     "WR_pw_set_cache_disabled"):
            self.assertIn(name, executor.event_dict)


if __name__ == "__main__":
    unittest.main()
