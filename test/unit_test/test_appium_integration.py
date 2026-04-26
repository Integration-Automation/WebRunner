import sys
import unittest
from unittest.mock import MagicMock, patch

from je_web_runner.utils.appium_integration.appium_driver import (
    AppiumIntegrationError,
    build_android_caps,
    build_ios_caps,
    quit_appium_session,
    start_appium_session,
)


class TestStartSession(unittest.TestCase):

    def test_invalid_url_raises(self):
        with self.assertRaises(AppiumIntegrationError):
            start_appium_session("ftp://x", {"platformName": "Android"})  # NOSONAR — fixture, asserts the validator rejects it

    def test_empty_caps_raises(self):
        with self.assertRaises(AppiumIntegrationError):
            start_appium_session("https://x", {})

    def test_starts_and_registers_on_wrapper(self):
        fake_remote = MagicMock()
        fake_remote.return_value = MagicMock()
        with patch(
            "je_web_runner.utils.appium_integration.appium_driver._require_appium",
            return_value=MagicMock(Remote=fake_remote),
        ), patch(
            "je_web_runner.utils.appium_integration.appium_driver.webdriver_wrapper_instance"
        ) as wrapper:
            driver = start_appium_session(
                "https://appium.example/wd/hub",
                {"platformName": "Android"},
            )
            self.assertIs(driver, fake_remote.return_value)
            self.assertIs(wrapper.current_webdriver, fake_remote.return_value)


class TestQuitSession(unittest.TestCase):

    def test_quit_when_no_driver_is_noop(self):
        with patch(
            "je_web_runner.utils.appium_integration.appium_driver.webdriver_wrapper_instance"
        ) as wrapper:
            wrapper.current_webdriver = None
            quit_appium_session()  # should not raise

    def test_quit_calls_driver_quit(self):
        with patch(
            "je_web_runner.utils.appium_integration.appium_driver.webdriver_wrapper_instance"
        ) as wrapper:
            driver = MagicMock()
            wrapper.current_webdriver = driver
            quit_appium_session()
            driver.quit.assert_called_once()
            self.assertIsNone(wrapper.current_webdriver)


class TestCaps(unittest.TestCase):

    def test_android_caps_shape(self):
        # Use a placeholder path that's never opened — the test only
        # validates the capability dict shape, so SonarCloud S5443 about
        # ``/tmp`` writability would be a false positive on a real path.
        caps = build_android_caps("./fixtures/app.apk", platform_version="14")
        self.assertEqual(caps["platformName"], "Android")
        self.assertEqual(caps["appium:platformVersion"], "14")
        self.assertEqual(caps["appium:app"], "./fixtures/app.apk")
        self.assertEqual(caps["appium:automationName"], "UiAutomator2")

    def test_ios_caps_shape(self):
        caps = build_ios_caps("./fixtures/app.app", device_name="iPhone 14")
        self.assertEqual(caps["platformName"], "iOS")
        self.assertEqual(caps["appium:deviceName"], "iPhone 14")
        self.assertEqual(caps["appium:automationName"], "XCUITest")

    def test_extra_caps_merge(self):
        caps = build_android_caps("./fixtures/x.apk", extra={"appium:autoGrantPermissions": True})
        self.assertTrue(caps["appium:autoGrantPermissions"])


class TestSoftDependency(unittest.TestCase):

    def test_missing_appium_raises_install_hint(self):
        with patch.dict(sys.modules, {"appium": None}):
            with self.assertRaises(AppiumIntegrationError):
                start_appium_session("https://x", {"platformName": "Android"})


if __name__ == "__main__":
    unittest.main()
