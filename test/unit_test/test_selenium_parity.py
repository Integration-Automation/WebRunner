"""Selenium commands matching Playwright ones (progress #19): waits, raw selectors, dialogs, CDP emulation."""
import unittest
from unittest.mock import MagicMock, patch

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By

from je_web_runner.element.web_element_wrapper import WebElementWrapper, web_element_wrapper
from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.executor.action_executor import executor
from je_web_runner.webdriver._wrapper_mixins._parity_mixin import resolve_by
from je_web_runner.webdriver.webdriver_wrapper import WebDriverWrapper


def _wrapper(driver=None):
    wrapper = WebDriverWrapper()
    wrapper.current_webdriver = driver or MagicMock()
    return wrapper


class TestWaits(unittest.TestCase):

    def setUp(self):
        saved = web_element_wrapper.current_web_element
        self.addCleanup(setattr, web_element_wrapper, "current_web_element", saved)

    def test_wait_for_visible_element_sets_the_current_element(self):
        driver = MagicMock()
        element = driver.find_element.return_value
        element.is_displayed.return_value = True
        self.assertIs(_wrapper(driver).wait_for_element("#pay", timeout=1), element)
        driver.find_element.assert_called_with(By.CSS_SELECTOR, "#pay")
        self.assertIs(web_element_wrapper.current_web_element, element)

    def test_a_wait_that_runs_out_raises(self):
        driver = MagicMock()
        driver.find_element.return_value.is_displayed.return_value = False
        with self.assertRaises(TimeoutException):
            _wrapper(driver).wait_for_element("#pay", timeout=0.2)

    def test_url_title_and_ready_state(self):
        driver = MagicMock()
        driver.current_url = "https://shop.example/checkout"
        driver.title = "Checkout"
        driver.execute_script.return_value = "complete"
        wrapper = _wrapper(driver)
        self.assertTrue(wrapper.wait_for_url("/checkout", timeout=1))
        self.assertTrue(wrapper.wait_for_title("Check", timeout=1))
        self.assertTrue(wrapper.wait_for_ready_state(timeout=1))

    def test_unknown_state_or_strategy_raises(self):
        with self.assertRaises(WebRunnerException):
            _wrapper().wait_for_element("#x", state="gone")
        with self.assertRaises(WebRunnerException):
            resolve_by("shadow")
        self.assertEqual(resolve_by("XPATH"), By.XPATH)
        self.assertEqual(resolve_by("link text"), By.LINK_TEXT)


class TestRawSelectorsAndDialogs(unittest.TestCase):

    def setUp(self):
        saved = (web_element_wrapper.current_web_element, web_element_wrapper.current_web_element_list)

        def restore():
            web_element_wrapper.current_web_element, web_element_wrapper.current_web_element_list = saved
        self.addCleanup(restore)

    def test_find_by_raw_selector(self):
        driver = MagicMock()
        wrapper = _wrapper(driver)
        self.assertIs(wrapper.find_element_by("//button", by="xpath"), driver.find_element.return_value)
        driver.find_element.assert_called_once_with(By.XPATH, "//button")
        self.assertIs(web_element_wrapper.current_web_element, driver.find_element.return_value)
        wrapper.find_elements_by("li")
        self.assertIs(web_element_wrapper.current_web_element_list, driver.find_elements.return_value)

    def test_alerts(self):
        driver = MagicMock()
        alert = driver.switch_to.alert
        alert.text = "Name?"
        wrapper = _wrapper(driver)
        self.assertEqual(wrapper.alert_text(), "Name?")
        wrapper.alert_accept(prompt_text="Ann")
        alert.send_keys.assert_called_once_with("Ann")
        alert.accept.assert_called_once_with()
        wrapper.alert_dismiss()
        alert.dismiss.assert_called_once_with()


class TestCdpEmulation(unittest.TestCase):

    def _calls(self, driver):
        return {call.args[0]: call.args[1] for call in driver.execute_cdp_cmd.call_args_list}

    def test_named_device(self):
        driver = MagicMock()
        wrapper = _wrapper(driver)
        name = wrapper.list_devices()[0]
        wrapper.emulate_device(name)
        calls = self._calls(driver)
        self.assertIn("Emulation.setDeviceMetricsOverride", calls)
        self.assertIn("userAgent", calls["Emulation.setUserAgentOverride"])

    def test_permissions_map_playwright_names_to_cdp(self):
        driver = MagicMock()
        wrapper = _wrapper(driver)
        wrapper.grant_permissions(["geolocation", "camera", "clipboard-read"], origin="https://x.example")
        params = self._calls(driver)["Browser.grantPermissions"]
        self.assertEqual(params["permissions"], ["clipboardReadWrite", "geolocation", "videoCapture"])
        self.assertEqual(params["origin"], "https://x.example")
        wrapper.clear_permissions()
        self.assertIn("Browser.resetPermissions", self._calls(driver))

    def test_clock_freeze_patches_current_and_future_documents(self):
        driver = MagicMock()
        _wrapper(driver).clock_freeze("2026-01-01T00:00:00Z")
        script = self._calls(driver)["Page.addScriptToEvaluateOnNewDocument"]["source"]
        self.assertIn(str(1767225600000), script)
        driver.execute_script.assert_called_once_with(script)


class TestElementCommands(unittest.TestCase):

    def setUp(self):
        self.wrapper = WebElementWrapper()
        self.element = MagicMock()
        self.wrapper.current_web_element = self.element

    def test_check_and_uncheck_only_click_when_needed(self):
        self.element.is_selected.return_value = False
        self.wrapper.check()
        self.wrapper.uncheck()
        self.assertEqual(self.element.click.call_count, 1)

    def test_text_html_and_hover(self):
        self.element.text = "Pay now"
        self.element.get_attribute.return_value = "<b>Pay</b> now"
        self.assertEqual(self.wrapper.inner_text(), "Pay now")
        self.assertEqual(self.wrapper.inner_html(), "<b>Pay</b> now")
        with patch("je_web_runner.element.web_element_wrapper.ActionChains") as chains:
            self.wrapper.hover()
        chains.return_value.move_to_element.assert_called_once_with(self.element)

    def test_failures_raise(self):
        self.wrapper.current_web_element = None
        with self.assertRaises(AttributeError):
            self.wrapper.inner_text()


class TestCommands(unittest.TestCase):

    def test_commands_are_registered(self):
        for name in ("WR_wait_for_element", "WR_wait_for_url", "WR_wait_for_title", "WR_wait_for_ready_state",
                     "WR_find_element_by", "WR_find_elements_by", "WR_alert_accept", "WR_alert_dismiss",
                     "WR_alert_text", "WR_emulate_device", "WR_list_devices", "WR_grant_permissions",
                     "WR_clear_permissions", "WR_clock_freeze", "WR_element_check", "WR_element_uncheck",
                     "WR_element_hover", "WR_element_inner_text", "WR_element_inner_html"):
            self.assertIn(name, executor.event_dict)


if __name__ == "__main__":
    unittest.main()
