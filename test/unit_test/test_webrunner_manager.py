"""Unit tests for WebdriverManager multi-driver coordination."""
import unittest
from unittest.mock import MagicMock

from selenium.common.exceptions import WebDriverException

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


class TestWrapperSingletonIsDetached(unittest.TestCase):
    """The manager owns raw Selenium handles, so closing one must also clear
    the shared wrapper singleton — otherwise it keeps serving a dead driver
    (and a stale ActionChains) to whoever calls next."""

    def setUp(self):
        self._saved_driver = webdriver_wrapper_instance.current_webdriver
        self._saved_chain = webdriver_wrapper_instance._action_chain

    def tearDown(self):
        webdriver_wrapper_instance.current_webdriver = self._saved_driver
        webdriver_wrapper_instance._action_chain = self._saved_chain

    def test_quit_detaches_wrapper(self):
        manager = WebdriverManager()
        driver = MagicMock(name="driver")
        manager._current_webdriver_list = [driver]
        webdriver_wrapper_instance.set_active_driver(driver)

        manager.quit()

        self.assertIsNone(webdriver_wrapper_instance.current_webdriver)
        self.assertIsNone(webdriver_wrapper_instance._action_chain)

    def test_close_current_detaches_wrapper(self):
        manager = WebdriverManager()
        driver = MagicMock(name="driver")
        manager._current_webdriver_list = [driver]
        manager.current_webdriver = driver
        webdriver_wrapper_instance.set_active_driver(driver)

        manager.close_current_webdriver()

        self.assertIsNone(webdriver_wrapper_instance.current_webdriver)

    def test_close_choose_leaves_unrelated_active_driver_alone(self):
        manager = WebdriverManager()
        driver0, driver1 = MagicMock(name="driver0"), MagicMock(name="driver1")
        manager._current_webdriver_list = [driver0, driver1]
        # The wrapper is driving driver0; closing driver1 must not disturb it.
        webdriver_wrapper_instance.set_active_driver(driver0)

        manager.close_choose_webdriver(1)

        self.assertIs(webdriver_wrapper_instance.current_webdriver, driver0)


class TestQuitIsResilient(unittest.TestCase):
    """One driver failing to quit must not strand the remaining browsers."""

    def test_quit_continues_past_failing_driver(self):
        manager = WebdriverManager()
        bad = MagicMock(name="bad")
        bad.quit.side_effect = RuntimeError("driver already dead")
        good_before, good_after = MagicMock(name="before"), MagicMock(name="after")
        manager._current_webdriver_list = [good_before, bad, good_after]

        with self.assertRaises(WebDriverException):
            manager.quit()

        # Every driver gets a quit() attempt, including the one queued after
        # the failure — otherwise it leaks as an orphan browser process.
        good_before.quit.assert_called_once()
        good_after.quit.assert_called_once()
        self.assertEqual(manager._current_webdriver_list, [])
        self.assertIsNone(manager.current_webdriver)

    def test_quit_clears_state_on_success(self):
        manager = WebdriverManager()
        driver = MagicMock(name="driver")
        manager._current_webdriver_list = [driver]
        manager.current_webdriver = driver

        manager.quit()

        driver.quit.assert_called_once()
        self.assertEqual(manager._current_webdriver_list, [])
        self.assertIsNone(manager.current_webdriver)


class TestCloseClearsCurrentDriver(unittest.TestCase):
    """A closed driver must never stay installed as ``current_webdriver``."""

    def test_close_current_webdriver_clears_reference(self):
        manager = WebdriverManager()
        driver = MagicMock(name="driver")
        manager._current_webdriver_list = [driver]
        manager.current_webdriver = driver

        manager.close_current_webdriver()

        driver.close.assert_called_once()
        self.assertIsNone(manager.current_webdriver)
        self.assertEqual(manager._current_webdriver_list, [])

    def test_failed_close_keeps_driver_tracked(self):
        manager = WebdriverManager()
        driver = MagicMock(name="driver")
        driver.close.side_effect = RuntimeError("close failed")
        manager._current_webdriver_list = [driver]
        manager.current_webdriver = driver

        manager.close_current_webdriver()

        # close() blew up, so the driver stays tracked and a later quit()
        # can still reclaim the process.
        self.assertEqual(manager._current_webdriver_list, [driver])

    def test_close_choose_webdriver_removes_only_that_index(self):
        manager = WebdriverManager()
        driver0, driver1 = MagicMock(name="driver0"), MagicMock(name="driver1")
        manager._current_webdriver_list = [driver0, driver1]
        manager.current_webdriver = driver1

        manager.close_choose_webdriver(1)

        driver1.close.assert_called_once()
        driver0.close.assert_not_called()
        self.assertEqual(manager._current_webdriver_list, [driver0])
        self.assertIsNone(manager.current_webdriver)


if __name__ == "__main__":
    unittest.main()
