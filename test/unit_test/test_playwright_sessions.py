"""Several Playwright browsers at once, switched by index (progress #19, last Playwright gap)."""
import unittest
from unittest.mock import MagicMock, patch

from je_web_runner.utils.executor.action_executor import executor
from je_web_runner.webdriver import playwright_wrapper as pw_module
from je_web_runner.webdriver.playwright_wrapper import PlaywrightBackendError, PlaywrightWrapper


def _fake_runtime():
    playwright = MagicMock()

    def launch_for(name):
        def launch(**_kwargs):
            browser = MagicMock(name=f"{name}-browser")
            page = MagicMock(name=f"{name}-page")
            page.url = "about:blank"
            browser.new_context.return_value.new_page.return_value = page
            return browser
        return launch

    for name in ("chromium", "firefox", "webkit"):
        getattr(playwright, name).launch.side_effect = launch_for(name)
    factory = MagicMock()
    factory.start.return_value = playwright
    starter = MagicMock(return_value=factory)
    return playwright, factory, patch.object(pw_module, "_require_playwright", return_value=starter)


class TestSessions(unittest.TestCase):

    def setUp(self):
        self.playwright, self.factory, runtime = _fake_runtime()
        runtime.start()
        self.addCleanup(runtime.stop)
        self.wrapper = PlaywrightWrapper()

    def test_second_browser_reuses_the_runtime_and_switching_moves_the_commands(self):
        self.wrapper.launch(browser="chromium")
        chromium_page = self.wrapper.page
        self.assertEqual(self.wrapper.new_browser(browser="firefox"), 1)
        firefox_page = self.wrapper.page
        self.assertEqual(self.factory.start.call_count, 1)
        self.assertEqual(self.wrapper.browser_count(), 2)
        self.wrapper.click("#a")
        firefox_page.click.assert_called_once_with("#a")
        self.wrapper.switch_browser(0)
        self.wrapper.click("#b")
        chromium_page.click.assert_called_once_with("#b")

    def test_settings_stay_with_their_browser(self):
        self.wrapper.launch(browser="chromium", context_options={"locale": "de-DE"})
        self.wrapper.new_browser(browser="webkit")
        self.assertEqual(self.wrapper._context_options, {})  # pylint: disable=protected-access
        self.wrapper.switch_browser(0)
        self.assertEqual(self.wrapper._context_options, {"locale": "de-DE"})  # pylint: disable=protected-access

    def test_close_browser_falls_back_to_another_and_quit_closes_all(self):
        self.wrapper.launch(browser="chromium")
        first_browser = self.wrapper.browser
        self.wrapper.new_browser(browser="firefox")
        second_browser = self.wrapper.browser
        self.wrapper.close_browser()
        second_browser.close.assert_called_once_with()
        self.assertIs(self.wrapper.browser, first_browser)
        self.assertEqual(self.wrapper.browser_count(), 1)
        self.wrapper.new_browser(browser="webkit")
        third_browser = self.wrapper.browser
        self.wrapper.quit()
        first_browser.close.assert_called_once_with()
        third_browser.close.assert_called_once_with()
        self.playwright.stop.assert_called_once_with()
        self.assertEqual(self.wrapper.browser_count(), 0)

    def test_closing_the_last_browser_stops_the_runtime(self):
        self.wrapper.launch()
        self.wrapper.close_browser()
        self.playwright.stop.assert_called_once_with()
        with self.assertRaises(PlaywrightBackendError):
            _ = self.wrapper.page

    def test_bad_index_raises(self):
        self.wrapper.launch()
        with self.assertRaises(PlaywrightBackendError):
            self.wrapper.switch_browser(3)

    def test_commands_are_registered(self):
        for name in ("WR_pw_new_browser", "WR_pw_switch_browser", "WR_pw_close_browser", "WR_pw_browser_count"):
            self.assertIn(name, executor.event_dict)


if __name__ == "__main__":
    unittest.main()
