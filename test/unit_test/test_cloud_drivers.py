import unittest
from unittest.mock import MagicMock, patch

from je_web_runner.utils.cloud_grid.cloud_drivers import (
    CloudGridError,
    _hub_url_with_credentials,
    build_browserstack_capabilities,
    build_lambdatest_capabilities,
    build_saucelabs_capabilities,
    connect_browserstack,
    connect_lambdatest,
    connect_saucelabs,
    start_remote_driver,
)


class TestCapabilities(unittest.TestCase):

    def test_browserstack_caps_include_bstack_options(self):
        caps = build_browserstack_capabilities(
            browser_name="firefox", project="P", build="B", name="N",
        )
        self.assertEqual(caps["browserName"], "firefox")
        self.assertEqual(caps["bstack:options"]["projectName"], "P")
        self.assertEqual(caps["bstack:options"]["buildName"], "B")

    def test_saucelabs_caps_include_sauce_options(self):
        caps = build_saucelabs_capabilities(name="ci-run")
        self.assertEqual(caps["sauce:options"]["name"], "ci-run")

    def test_lambdatest_caps_include_lt_options(self):
        caps = build_lambdatest_capabilities(build="42")
        self.assertEqual(caps["LT:Options"]["build"], "42")

    def test_extra_caps_merge(self):
        caps = build_browserstack_capabilities(extra={"acceptInsecureCerts": True})
        self.assertTrue(caps["acceptInsecureCerts"])


class TestHubUrl(unittest.TestCase):

    def test_credentials_injected(self):
        url = _hub_url_with_credentials("https://hub.example/wd/hub", "alice", "secret")
        self.assertIn("alice:secret@hub.example", url)

    def test_special_chars_encoded(self):
        url = _hub_url_with_credentials("https://hub.example/wd/hub", "user@x", "p:w/")
        # @ becomes %40, : becomes %3A, / becomes %2F
        self.assertIn("user%40x:p%3Aw%2F@hub.example", url)

    def test_empty_creds_raise(self):
        with self.assertRaises(CloudGridError):
            _hub_url_with_credentials("https://hub.example/wd/hub", "", "k")
        with self.assertRaises(CloudGridError):
            _hub_url_with_credentials("https://hub.example/wd/hub", "u", "")

    def test_invalid_url_raises(self):
        with self.assertRaises(CloudGridError):
            _hub_url_with_credentials("not-a-url", "u", "k")


class TestConnect(unittest.TestCase):

    def test_connect_browserstack_uses_default_hub(self):
        fake_driver = MagicMock()
        with patch("je_web_runner.utils.cloud_grid.cloud_drivers.webdriver.Remote",
                   return_value=fake_driver) as remote_mock, \
                patch("je_web_runner.utils.cloud_grid.cloud_drivers.webdriver_wrapper_instance"):
            driver = connect_browserstack("alice", "secret")
            self.assertIs(driver, fake_driver)
            kwargs = remote_mock.call_args.kwargs
            self.assertIn("hub-cloud.browserstack.com", kwargs["command_executor"])

    def test_connect_saucelabs_uses_default_hub(self):
        fake_driver = MagicMock()
        with patch("je_web_runner.utils.cloud_grid.cloud_drivers.webdriver.Remote",
                   return_value=fake_driver) as remote_mock, \
                patch("je_web_runner.utils.cloud_grid.cloud_drivers.webdriver_wrapper_instance"):
            connect_saucelabs("alice", "secret")
            self.assertIn("ondemand.us-west-1.saucelabs.com", remote_mock.call_args.kwargs["command_executor"])

    def test_connect_lambdatest_uses_default_hub(self):
        fake_driver = MagicMock()
        with patch("je_web_runner.utils.cloud_grid.cloud_drivers.webdriver.Remote",
                   return_value=fake_driver) as remote_mock, \
                patch("je_web_runner.utils.cloud_grid.cloud_drivers.webdriver_wrapper_instance"):
            connect_lambdatest("alice", "secret")
            self.assertIn("hub.lambdatest.com", remote_mock.call_args.kwargs["command_executor"])

    def test_start_remote_driver_registers_on_wrapper(self):
        fake_driver = MagicMock()
        with patch("je_web_runner.utils.cloud_grid.cloud_drivers.webdriver.Remote",
                   return_value=fake_driver), \
                patch("je_web_runner.utils.cloud_grid.cloud_drivers.webdriver_wrapper_instance") as wrapper:
            start_remote_driver("https://hub/wd/hub", {"browserName": "chrome"})
            self.assertIs(wrapper.current_webdriver, fake_driver)


if __name__ == "__main__":
    unittest.main()
