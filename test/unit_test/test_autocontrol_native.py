"""The native ``WR_ac_*`` commands (file dialog, image on screen) with AutoControl faked."""
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from selenium.webdriver import Firefox
from selenium.webdriver.chromium.webdriver import ChromiumDriver

from je_web_runner.mcp_server import _policy
from je_web_runner.utils.autocontrol_bridge import bridge, native
from je_web_runner.utils.autocontrol_bridge.bridge import AutoControlBridgeError
from je_web_runner.utils.executor.action_executor import executor
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
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


class TestBasicAuth(_WithDriver):

    driver = _chrome()
    password = "S3cret,AC_shell_command!"  # a refused name inside a password is only text to type

    def setUp(self):
        super().setUp()
        self.focused = True
        self.driver.execute_script.reset_mock()
        self.driver.execute_script.side_effect = lambda script, *args: (
            self.focused if "hasFocus" in script else "Mozilla/5.0 Chrome/140")
        self.addCleanup(setattr, self.driver.execute_script, "side_effect", None)
        self.fake = MagicMock()
        self.fake.known_commands.return_value = ["AC_write_secret", "AC_type_keyboard"]
        self.fake.execute_action.side_effect = lambda actions, raise_on_error: {
            str(index): None for index, _action in enumerate(actions)}
        for target in (native, bridge):
            self._start(patch.object(target, "ac_executor", return_value=self.fake))
        self._start(patch.object(native, "ac_run", return_value={"return": 13, "tab": 9}))
        self._start(patch.object(native.time, "sleep"))
        self._start(patch.dict(os.environ, {"WR_TEST_USER": "Al1ce", "WR_TEST_PASS": self.password}))

    def _start(self, patcher):
        mocked = patcher.start()
        self.addCleanup(patcher.stop)
        return mocked

    def _typed(self):
        return self.fake.execute_action.call_args.args[0]

    def test_types_username_tab_password_then_enter(self):
        with self.assertLogs(web_runner_logger, level="INFO") as logs:
            self.assertIsNone(native.basic_auth_native("WR_TEST_USER", "WR_TEST_PASS"))
        self.assertEqual(self._typed(), [
            ["AC_write_secret", {"secret": "Al1ce"}], ["AC_type_keyboard", {"keycode": "tab"}],
            ["AC_write_secret", {"secret": self.password}], ["AC_type_keyboard", {"keycode": "return"}]])
        self.assertNotIn("S3cret", "\n".join(logs.output))
        self.assertNotIn("Al1ce", "\n".join(logs.output))

    def test_without_submit_enter_is_not_pressed(self):
        native.basic_auth_native("WR_TEST_USER", "WR_TEST_PASS", submit=False)
        self.assertEqual(len(self._typed()), 3)

    def test_a_url_is_opened_without_waiting_for_the_page(self):
        native.basic_auth_native("WR_TEST_USER", "WR_TEST_PASS", url="http://127.0.0.1:8080/private")
        self.driver.execute_script.assert_called_with(
            "window.location.assign(arguments[0]);", "http://127.0.0.1:8080/private")

    def test_a_browser_without_the_keyboard_focus_is_refused_before_typing(self):
        self.focused = False
        with self.assertRaisesRegex(AutoControlBridgeError, "keyboard focus"):
            native.basic_auth_native("WR_TEST_USER", "WR_TEST_PASS", url="http://127.0.0.1:8080/private")
        self.assertNotIn("window.location.assign(arguments[0]);",
                         [call.args[0] for call in self.driver.execute_script.call_args_list])
        self.fake.execute_action.assert_not_called()

    def test_bad_input_is_refused_before_typing_and_never_echoes_a_value(self):
        cases = [(("WR_TEST_MISSING", "WR_TEST_PASS"), {}, "WR_TEST_MISSING"),
                 (("", "WR_TEST_PASS"), {}, "name of an environment variable"),
                 (("WR_TEST_USER", "WR_TEST_PASS"), {"url": "javascript:alert(1)"}, "http"),
                 (("WR_TEST_USER", "WR_TEST_BROKEN"), {}, "WR_TEST_BROKEN")]
        with patch.dict(os.environ, {"WR_TEST_BROKEN": "Zq7x\nVv9w"}):
            for args, kwargs, expected in cases:
                with self.subTest(args=args, kwargs=kwargs):
                    with self.assertRaisesRegex(AutoControlBridgeError, expected) as caught:
                        native.basic_auth_native(*args, **kwargs)
                    self.assertNotIn("S3cret", str(caught.exception))
                    self.assertNotIn("Zq7x", str(caught.exception))
        self.fake.execute_action.assert_not_called()

    def test_an_autocontrol_without_secret_typing_is_refused(self):
        self.fake.known_commands.return_value = ["AC_write", "AC_type_keyboard"]
        with self.assertRaisesRegex(AutoControlBridgeError, "upgrade je_auto_control"):
            native.basic_auth_native("WR_TEST_USER", "WR_TEST_PASS")
        self.fake.execute_action.assert_not_called()

    def test_a_headless_browser_is_refused_before_typing(self):
        webdriver_wrapper_instance.current_webdriver = _chrome("HeadlessChrome/140")
        with self.assertRaises(AutoControlBridgeError):
            native.basic_auth_native("WR_TEST_USER", "WR_TEST_PASS")
        self.fake.execute_action.assert_not_called()

    def test_the_action_file_names_variables_not_values(self):
        record, failed = executor.collect_action_results(
            [["WR_ac_basic_auth", {"username_env": "WR_TEST_USER", "password_env": "WR_TEST_PASS"}]])
        self.assertEqual(failed, [], record)
        self.assertNotIn("S3cret", repr(record))


class TestCommands(unittest.TestCase):

    def test_registered_and_denied_over_mcp(self):
        for name in ("WR_ac_fill_native_file_dialog", "WR_ac_assert_image_on_screen", "WR_ac_basic_auth"):
            self.assertIn(name, executor.event_dict)
            self.assertIn(name, _policy.UNSAFE_COMMANDS)


if __name__ == "__main__":
    unittest.main()
