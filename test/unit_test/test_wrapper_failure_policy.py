"""What a failed Selenium wrapper call does to its action: deprecated pass, raise, or explicit pass."""
import unittest
import warnings
from unittest.mock import MagicMock

from selenium.common.exceptions import WebDriverException

from je_web_runner.element.web_element_wrapper import web_element_wrapper
from je_web_runner.utils.executor.action_executor import executor
from je_web_runner.utils.test_record.test_record_class import test_record_instance
from je_web_runner.utils.test_record.wrapper_failures import wrapper_failure_policy
from je_web_runner.webdriver.webdriver_wrapper import webdriver_wrapper_instance


class TestWrapperFailurePolicy(unittest.TestCase):

    def setUp(self):
        self.driver = MagicMock()
        self.driver.get.side_effect = WebDriverException("net::ERR_NAME_NOT_RESOLVED")
        saved = (webdriver_wrapper_instance.current_webdriver, web_element_wrapper.current_web_element,
                 wrapper_failure_policy.raise_errors, set(wrapper_failure_policy.warned),
                 test_record_instance.test_record_list, test_record_instance.init_record)
        webdriver_wrapper_instance.current_webdriver = self.driver
        wrapper_failure_policy.raise_errors = None
        wrapper_failure_policy.warned = set()
        test_record_instance.test_record_list = []
        test_record_instance.set_record_enable(True)
        self.addCleanup(self._restore, saved)

    @staticmethod
    def _restore(saved):
        (webdriver_wrapper_instance.current_webdriver, web_element_wrapper.current_web_element,
         wrapper_failure_policy.raise_errors, wrapper_failure_policy.warned,
         test_record_instance.test_record_list, test_record_instance.init_record) = saved

    def test_the_default_still_passes_but_warns_once_per_method(self):
        with warnings.catch_warnings(record=True) as caught, self.assertLogs("WEBRunner", "WARNING") as logs:
            warnings.simplefilter("always")
            webdriver_wrapper_instance.to_url("https://nowhere.test/")
            webdriver_wrapper_instance.to_url("https://nowhere.test/")
        deprecations = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        self.assertEqual(len(deprecations), 1)
        self.assertIn("webdriver wrapper to_url failed", str(deprecations[0].message))
        self.assertIn("WR_set_raise_wrapper_errors", "".join(logs.output))
        self.assertEqual(len(test_record_instance.test_record_list), 2)
        self.assertIn("WebDriverException", test_record_instance.test_record_list[0]["program_exception"])

    def test_strict_mode_raises_after_recording(self):
        executor.set_raise_wrapper_errors(True)
        with self.assertRaises(WebDriverException):
            webdriver_wrapper_instance.to_url("https://nowhere.test/")
        self.assertIn("WebDriverException", test_record_instance.test_record_list[-1]["program_exception"])

    def test_explicitly_off_passes_silently(self):
        executor.set_raise_wrapper_errors(False)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            webdriver_wrapper_instance.to_url("https://nowhere.test/")
        self.assertEqual([w for w in caught if issubclass(w.category, DeprecationWarning)], [])

    def test_an_action_file_opts_in_and_a_wrong_assertion_fails(self):
        element = MagicMock()
        element.get_attribute.return_value = "Sign out"
        element.text = "Sign out"
        element.tag_name = "button"
        web_element_wrapper.current_web_element = element
        record, failed = executor.collect_action_results([
            ["WR_set_raise_wrapper_errors", [True]],
            ["WR_to_url", {"url": "https://nowhere.test/"}],
            ["WR_element_assert", {"check_dict": {"tag_name": "a"}}],
        ])
        self.assertEqual(len(failed), 2)
        self.assertIn("WebDriverException", record[failed[0]])

    def test_the_old_pass_is_kept_without_the_switch(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _record, failed = executor.collect_action_results([["WR_to_url", {"url": "https://nowhere.test/"}]])
        self.assertEqual(failed, [])


if __name__ == "__main__":
    unittest.main()
