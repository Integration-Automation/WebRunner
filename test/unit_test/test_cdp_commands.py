import unittest
from unittest.mock import MagicMock, patch

from je_web_runner.utils.cdp.cdp_commands import (
    CDPError,
    playwright_cdp,
    reset_playwright_cdp_sessions,
    selenium_cdp,
)


class TestSeleniumCDP(unittest.TestCase):

    def test_no_driver_raises(self):
        with patch("je_web_runner.utils.cdp.cdp_commands.webdriver_wrapper_instance") as wrapper:
            wrapper.current_webdriver = None
            with self.assertRaises(CDPError):
                selenium_cdp("Network.enable")

    def test_non_cdp_driver_raises(self):
        with patch("je_web_runner.utils.cdp.cdp_commands.webdriver_wrapper_instance") as wrapper:
            driver = object()  # no execute_cdp_cmd
            wrapper.current_webdriver = driver
            with self.assertRaises(CDPError):
                selenium_cdp("Network.enable")

    def test_dispatches_to_driver(self):
        with patch("je_web_runner.utils.cdp.cdp_commands.webdriver_wrapper_instance") as wrapper:
            driver = MagicMock()
            wrapper.current_webdriver = driver
            driver.execute_cdp_cmd.return_value = {"ok": True}
            self.assertEqual(selenium_cdp("Network.enable", {"a": 1}), {"ok": True})
            driver.execute_cdp_cmd.assert_called_once_with("Network.enable", {"a": 1})


class TestPlaywrightCDP(unittest.TestCase):

    def setUp(self):
        reset_playwright_cdp_sessions()

    def test_creates_and_caches_session(self):
        with patch("je_web_runner.utils.cdp.cdp_commands.playwright_wrapper_instance") as wrapper:
            page = MagicMock(name="page")
            wrapper.page = page
            session = MagicMock()
            session.send.return_value = {"x": 1}
            wrapper.context.new_cdp_session.return_value = session
            self.assertEqual(playwright_cdp("Page.enable"), {"x": 1})
            self.assertEqual(playwright_cdp("Page.enable"), {"x": 1})
            wrapper.context.new_cdp_session.assert_called_once_with(page)

    def test_session_open_failure_wrapped(self):
        with patch("je_web_runner.utils.cdp.cdp_commands.playwright_wrapper_instance") as wrapper:
            wrapper.page = MagicMock()
            wrapper.context.new_cdp_session.side_effect = RuntimeError("firefox")
            with self.assertRaises(CDPError):
                playwright_cdp("Page.enable")


if __name__ == "__main__":
    unittest.main()
