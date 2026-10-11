"""One merged set of Playwright context options; rebuilding keeps cookies, storage and the page URL."""
import unittest
from unittest.mock import MagicMock, patch

from je_web_runner.utils.executor.action_executor import executor
from je_web_runner.webdriver import playwright_wrapper as pw_module
from je_web_runner.webdriver.playwright_wrapper import PlaywrightWrapper


def _context(url="https://shop.example/cart"):
    page = MagicMock()
    page.url = url
    context = MagicMock()
    context.new_page.return_value = page
    context.storage_state.return_value = {"cookies": [{"name": "sid"}], "origins": []}
    return context


def _launch(**launch_kwargs):
    browser = MagicMock()
    browser.new_context.side_effect = lambda **kwargs: _context()
    playwright = MagicMock()
    playwright.chromium.launch.return_value = browser
    playwright.devices = {"iPhone 13": {"viewport": {"width": 390, "height": 844}, "is_mobile": True}}
    factory = MagicMock()
    factory.start.return_value = playwright
    with patch.object(pw_module, "_require_playwright", return_value=MagicMock(return_value=factory)):
        wrapper = PlaywrightWrapper()
        wrapper.launch(browser="chromium", **launch_kwargs)
    return wrapper, browser


def _last_options(browser):
    return browser.new_context.call_args.kwargs


class TestMergedOptions(unittest.TestCase):

    def test_launch_takes_context_options(self):
        _wrapper, browser = _launch(context_options={"user_agent": "bot/1", "locale": "de-DE"})
        self.assertEqual(_last_options(browser), {"user_agent": "bot/1", "locale": "de-DE"})

    def test_settings_accumulate_instead_of_replacing_each_other(self):
        wrapper, browser = _launch()
        wrapper.set_timezone("Asia/Tokyo")
        wrapper.set_locale("ja-JP", accept_language="ja")
        wrapper.start_emulation("iPhone 13")
        options = _last_options(browser)
        self.assertEqual(options["timezone_id"], "Asia/Tokyo")
        self.assertEqual(options["locale"], "ja-JP")
        self.assertEqual(options["extra_http_headers"], {"Accept-Language": "ja"})
        self.assertTrue(options["is_mobile"])

    def test_stop_emulation_removes_only_the_device_options(self):
        wrapper, browser = _launch()
        wrapper.set_timezone("Asia/Tokyo")
        wrapper.start_emulation("iPhone 13")
        wrapper.stop_emulation()
        options = _last_options(browser)
        self.assertNotIn("is_mobile", options)
        self.assertNotIn("viewport", options)
        self.assertEqual(options["timezone_id"], "Asia/Tokyo")

    def test_har_recording_keeps_other_options_and_stop_removes_it(self):
        wrapper, browser = _launch()
        wrapper.set_timezone("UTC")
        wrapper.start_har_recording("run.har", content="embed")
        self.assertEqual(_last_options(browser)["record_har_path"], "run.har")
        self.assertEqual(_last_options(browser)["timezone_id"], "UTC")
        wrapper.stop_har_recording()
        self.assertNotIn("record_har_path", _last_options(browser))
        self.assertEqual(_last_options(browser)["timezone_id"], "UTC")

    def test_generic_setter_and_user_agent(self):
        wrapper, browser = _launch()
        wrapper.set_context_options(color_scheme="dark", reduced_motion="reduce")
        wrapper.set_user_agent("bot/2")
        options = _last_options(browser)
        self.assertEqual(options["color_scheme"], "dark")
        self.assertEqual(options["user_agent"], "bot/2")


class TestRebuildKeepsState(unittest.TestCase):

    def test_cookies_storage_and_url_survive_a_rebuild(self):
        wrapper, browser = _launch()
        old_context = wrapper.context
        old_context.pages = [wrapper.page]
        wrapper.set_timezone("Europe/Berlin")
        self.assertEqual(_last_options(browser)["storage_state"],
                         {"cookies": [{"name": "sid"}], "origins": []})
        old_context.close.assert_called_once()
        wrapper.page.goto.assert_called_once_with("https://shop.example/cart")

    def test_blank_pages_are_not_reopened(self):
        wrapper, _browser = _launch()
        wrapper.page.url = "about:blank"
        wrapper.set_timezone("UTC")
        wrapper.page.goto.assert_not_called()


class TestHeadersAndStorage(unittest.TestCase):

    def test_extra_headers_apply_to_the_live_context_and_merge(self):
        wrapper, browser = _launch()
        wrapper.set_locale("fr-FR", accept_language="fr")
        wrapper.set_extra_http_headers({"X-Test": "1"})
        wrapper.context.set_extra_http_headers.assert_called_once_with({"Accept-Language": "fr", "X-Test": "1"})
        self.assertEqual(browser.new_context.call_count, 2)  # launch + locale; headers need no rebuild

    def test_save_storage_state(self):
        wrapper, _browser = _launch()
        wrapper.save_storage_state("state.json")
        wrapper.context.storage_state.assert_called_with(path="state.json")


class TestCommands(unittest.TestCase):

    def test_new_commands_are_registered(self):
        for name in ("WR_pw_set_context_options", "WR_pw_set_user_agent",
                     "WR_pw_set_extra_http_headers", "WR_pw_save_storage_state"):
            self.assertIn(name, executor.event_dict)


if __name__ == "__main__":
    unittest.main()
