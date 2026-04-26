import unittest
from unittest.mock import MagicMock, patch

from je_web_runner.utils.service_worker import sw_control as sw
from je_web_runner.utils.service_worker.sw_control import ServiceWorkerError


class TestSeleniumSW(unittest.TestCase):

    def test_no_driver_raises(self):
        with patch("je_web_runner.utils.service_worker.sw_control.webdriver_wrapper_instance") as wrapper:
            wrapper.current_webdriver = None
            with self.assertRaises(ServiceWorkerError):
                sw.selenium_unregister_service_workers()

    def test_unregister_returns_results(self):
        with patch("je_web_runner.utils.service_worker.sw_control.webdriver_wrapper_instance") as wrapper:
            driver = MagicMock()
            wrapper.current_webdriver = driver
            driver.execute_async_script.return_value = [True, True]
            self.assertEqual(sw.selenium_unregister_service_workers(), [True, True])

    def test_clear_caches_returns_keys(self):
        with patch("je_web_runner.utils.service_worker.sw_control.webdriver_wrapper_instance") as wrapper:
            driver = MagicMock()
            wrapper.current_webdriver = driver
            driver.execute_async_script.return_value = ["a", "b"]
            self.assertEqual(sw.selenium_clear_caches(), ["a", "b"])

    def test_bypass_service_worker_dispatches_cdp(self):
        with patch(
            "je_web_runner.utils.service_worker.sw_control.selenium_cdp"
        ) as cdp_mock:
            sw.selenium_bypass_service_worker(True)
            cdp_mock.assert_called_once_with(
                "Network.setBypassServiceWorker", {"bypass": True}
            )


class TestPlaywrightSW(unittest.TestCase):

    def test_unregister_returns_results(self):
        with patch(
            "je_web_runner.utils.service_worker.sw_control.playwright_wrapper_instance"
        ) as wrapper:
            page = MagicMock()
            wrapper.page = page
            page.evaluate.return_value = [True]
            self.assertEqual(sw.playwright_unregister_service_workers(), [True])

    def test_clear_caches_returns_keys(self):
        with patch(
            "je_web_runner.utils.service_worker.sw_control.playwright_wrapper_instance"
        ) as wrapper:
            page = MagicMock()
            wrapper.page = page
            page.evaluate.return_value = ["v1", "v2"]
            self.assertEqual(sw.playwright_clear_caches(), ["v1", "v2"])

    def test_bypass_dispatches_to_cdp(self):
        with patch(
            "je_web_runner.utils.service_worker.sw_control.playwright_cdp"
        ) as cdp_mock:
            sw.playwright_bypass_service_worker(False)
            cdp_mock.assert_called_once_with(
                "Network.setBypassServiceWorker", {"bypass": False}
            )


if __name__ == "__main__":
    unittest.main()
