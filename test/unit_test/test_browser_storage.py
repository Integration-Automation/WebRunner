import unittest
from unittest.mock import MagicMock, patch

from je_web_runner.utils.storage import browser_storage as storage
from je_web_runner.utils.storage.browser_storage import StorageError


class TestSeleniumStorage(unittest.TestCase):

    def test_no_driver_raises(self):
        with patch("je_web_runner.utils.storage.browser_storage.webdriver_wrapper_instance") as wrapper:
            wrapper.current_webdriver = None
            with self.assertRaises(StorageError):
                storage.selenium_local_storage_set("k", "v")

    def test_local_storage_set_calls_execute_script(self):
        with patch("je_web_runner.utils.storage.browser_storage.webdriver_wrapper_instance") as wrapper:
            driver = MagicMock()
            wrapper.current_webdriver = driver
            storage.selenium_local_storage_set("k", "v")
            args = driver.execute_script.call_args[0]
            self.assertIn("localStorage.setItem", args[0])
            self.assertEqual(args[1:], ("k", "v"))

    def test_local_storage_all_empty_default(self):
        with patch("je_web_runner.utils.storage.browser_storage.webdriver_wrapper_instance") as wrapper:
            driver = MagicMock()
            wrapper.current_webdriver = driver
            driver.execute_script.return_value = None
            self.assertEqual(storage.selenium_local_storage_all(), {})

    def test_session_storage_clear(self):
        with patch("je_web_runner.utils.storage.browser_storage.webdriver_wrapper_instance") as wrapper:
            driver = MagicMock()
            wrapper.current_webdriver = driver
            storage.selenium_session_storage_clear()
            self.assertIn("sessionStorage.clear", driver.execute_script.call_args[0][0])

    def test_indexed_db_drop_passes_name(self):
        with patch("je_web_runner.utils.storage.browser_storage.webdriver_wrapper_instance") as wrapper:
            driver = MagicMock()
            wrapper.current_webdriver = driver
            storage.selenium_indexed_db_drop("mydb")
            self.assertEqual(driver.execute_script.call_args[0][1], "mydb")


class TestPlaywrightStorage(unittest.TestCase):

    def test_local_storage_set_calls_evaluate(self):
        with patch(
            "je_web_runner.utils.storage.browser_storage.playwright_wrapper_instance"
        ) as wrapper:
            page = MagicMock()
            wrapper.page = page
            storage.playwright_local_storage_set("k", "v")
            page.evaluate.assert_called_once()
            args = page.evaluate.call_args[0]
            self.assertEqual(args[1], ["k", "v"])

    def test_local_storage_all_returns_dict(self):
        with patch(
            "je_web_runner.utils.storage.browser_storage.playwright_wrapper_instance"
        ) as wrapper:
            page = MagicMock()
            wrapper.page = page
            page.evaluate.return_value = {"k": "v"}
            self.assertEqual(storage.playwright_local_storage_all(), {"k": "v"})

    def test_indexed_db_drop_calls_evaluate(self):
        with patch(
            "je_web_runner.utils.storage.browser_storage.playwright_wrapper_instance"
        ) as wrapper:
            page = MagicMock()
            wrapper.page = page
            storage.playwright_indexed_db_drop("mydb")
            self.assertEqual(page.evaluate.call_args[0][1], "mydb")


if __name__ == "__main__":
    unittest.main()
