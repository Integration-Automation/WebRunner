"""Unit tests for WebdriverManager multi-driver coordination."""
import unittest
from unittest.mock import MagicMock

from je_web_runner.manager.webrunner_manager import WebdriverManager
from je_web_runner.webdriver.webdriver_wrapper import webdriver_wrapper_instance


class TestChangeWebdriverRebindsActionChain(unittest.TestCase):
    """Switching drivers must rebind the wrapper's ActionChains to the new
    driver, not leave it pointing at the previously active one."""

    def setUp(self):
        self._saved_driver = webdriver_wrapper_instance.current_webdriver
        self._saved_chain = webdriver_wrapper_instance._action_chain

    def tearDown(self):
        webdriver_wrapper_instance.current_webdriver = self._saved_driver
        webdriver_wrapper_instance._action_chain = self._saved_chain

    def test_change_webdriver_rebinds_action_chain(self):
        manager = WebdriverManager()
        driver0, driver1 = MagicMock(name="driver0"), MagicMock(name="driver1")
        manager._current_webdriver_list = [driver0, driver1]

        manager.change_webdriver(0)
        self.assertIs(webdriver_wrapper_instance.current_webdriver, driver0)
        self.assertIs(webdriver_wrapper_instance._action_chain._driver, driver0)

        manager.change_webdriver(1)
        self.assertIs(webdriver_wrapper_instance.current_webdriver, driver1)
        # Must follow the switch — would be driver0 with the old stale binding.
        self.assertIs(webdriver_wrapper_instance._action_chain._driver, driver1)


class TestSetActiveDriver(unittest.TestCase):

    def setUp(self):
        self._saved_driver = webdriver_wrapper_instance.current_webdriver
        self._saved_chain = webdriver_wrapper_instance._action_chain

    def tearDown(self):
        webdriver_wrapper_instance.current_webdriver = self._saved_driver
        webdriver_wrapper_instance._action_chain = self._saved_chain

    def test_set_active_driver_builds_chain(self):
        driver = MagicMock(name="driver")
        webdriver_wrapper_instance.set_active_driver(driver)
        self.assertIs(webdriver_wrapper_instance.current_webdriver, driver)
        self.assertIs(webdriver_wrapper_instance._action_chain._driver, driver)

    def test_set_active_driver_none_clears_chain(self):
        webdriver_wrapper_instance.set_active_driver(None)
        self.assertIsNone(webdriver_wrapper_instance.current_webdriver)
        self.assertIsNone(webdriver_wrapper_instance._action_chain)


if __name__ == "__main__":
    unittest.main()
