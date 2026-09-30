"""The native ``WR_ac_*`` commands (file dialog, image on screen) with AutoControl faked."""
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from selenium.webdriver import Firefox
from selenium.webdriver.chromium.webdriver import ChromiumDriver

from je_web_runner.mcp_server import _policy
from je_web_runner.utils.autocontrol_bridge import native
from je_web_runner.utils.autocontrol_bridge.bridge import AutoControlBridgeError
from je_web_runner.utils.executor.action_executor import executor
from je_web_runner.webdriver.webdriver_wrapper import webdriver_wrapper_instance


def _chrome(user_agent="Mozilla/5.0 Chrome/140"):
    driver = MagicMock(spec=ChromiumDriver)
    driver.capabilities = {}
    driver.execute_script.return_value = user_agent
    return driver


class _WithDriver(unittest.TestCase):

    driver = None

    def setUp(self):
        previous = webdriver_wrapper_instance.current_webdriver
        webdriver_wrapper_instance.current_webdriver = self.driver
        self.addCleanup(setattr, webdriver_wrapper_instance, "current_webdriver", previous)


class TestVisibleBrowser(unittest.TestCase):

    def test_reasons(self):
        self.assertIsNone(native.invisible_reason(_chrome()))
        self.assertIn("headless", native.invisible_reason(_chrome("Mozilla/5.0 HeadlessChrome/140")))
        firefox = MagicMock(spec=Firefox)
        firefox.capabilities = {"moz:headless": True}
        self.assertIn("headless", native.invisible_reason(firefox))
        self.assertIn("remote", native.invisible_reason(MagicMock()))

    def test_no_driver_is_allowed_and_an_invisible_one_is_refused(self):
        previous = webdriver_wrapper_instance.current_webdriver
        try:
            webdriver_wrapper_instance.current_webdriver = None
            native.require_visible_browser()
            webdriver_wrapper_instance.current_webdriver = _chrome("HeadlessChrome")
            with self.assertRaisesRegex(AutoControlBridgeError, "this machine's screen"):
                native.require_visible_browser()
        finally:
            webdriver_wrapper_instance.current_webdriver = previous


class TestFileDialog(_WithDriver):

    driver = _chrome()

    def setUp(self):
        super().setUp()
        self.run_actions = self._start(patch.object(native, "ac_run_actions"))
        self._start(patch.object(native, "ac_run", return_value={"return": 13, "tab": 9}))
        self._start(patch.object(native.time, "sleep"))

    def _start(self, patcher):
        mocked = patcher.start()
        self.addCleanup(patcher.stop)
        return mocked

    def test_types_the_absolute_path_then_enter(self):
        typed = native.fill_native_file_dialog("reports/q3.pdf")
        self.assertEqual(typed, os.path.abspath("reports/q3.pdf"))
        self.run_actions.assert_called_once_with([
            ["AC_write", {"write_string": typed}], ["AC_type_keyboard", {"keycode": "return"}]])

    def test_without_submit_only_types(self):
        native.fill_native_file_dialog("a.txt", submit=False)
        self.assertEqual(len(self.run_actions.call_args.args[0]), 1)

    def test_bad_paths_are_refused_before_typing(self):
        for path in ("", "a\nb.txt", "a\tb", None):
            with self.subTest(path=path), self.assertRaises(AutoControlBridgeError):
                native.fill_native_file_dialog(path)
        self.run_actions.assert_not_called()

    def test_a_headless_browser_is_refused_before_typing(self):
        webdriver_wrapper_instance.current_webdriver = _chrome("HeadlessChrome/140")
        with self.assertRaises(AutoControlBridgeError):
            native.fill_native_file_dialog("a.txt")
        self.run_actions.assert_not_called()


class TestImageOnScreen(_WithDriver):

    driver = None

    def test_returns_the_centre_and_passes_the_threshold(self):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as image:
            path = image.name
        self.addCleanup(os.remove, path)
        with patch.object(native, "ac_run", return_value=(120, 45)) as run:
            self.assertEqual(native.assert_image_on_screen(path, detect_threshold=0.8), [120, 45])
        run.assert_called_once_with(["AC_locate_image_center", {"image": path, "detect_threshold": 0.8}])

    def test_a_missing_template_or_image_fails(self):
        with self.assertRaises(AutoControlBridgeError):
            native.assert_image_on_screen("no/such/template.png")
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as image:
            path = image.name
        self.addCleanup(os.remove, path)
        with patch.object(native, "ac_run", side_effect=AutoControlBridgeError("not found")), \
                self.assertRaises(AutoControlBridgeError):
            native.assert_image_on_screen(path)


class TestCommands(unittest.TestCase):

    def test_registered_and_denied_over_mcp(self):
        for name in ("WR_ac_fill_native_file_dialog", "WR_ac_assert_image_on_screen"):
            self.assertIn(name, executor.event_dict)
            self.assertIn(name, _policy.UNSAFE_COMMANDS)


if __name__ == "__main__":
    unittest.main()
