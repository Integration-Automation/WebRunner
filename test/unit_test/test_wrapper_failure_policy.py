"""What a failed Selenium wrapper call does to its action: fail by default, or pass when turned off."""
import unittest
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
                 wrapper_failure_policy.raise_errors, test_record_instance.test_record_list,
                 test_record_instance.init_record)
        webdriver_wrapper_instance.current_webdriver = self.driver
        test_record_instance.test_record_list = []
        test_record_instance.set_record_enable(True)
        self.addCleanup(self._restore, saved)

    @staticmethod
    def _restore(saved):
        (webdriver_wrapper_instance.current_webdriver, web_element_wrapper.current_web_element,
         wrapper_failure_policy.raise_errors, test_record_instance.test_record_list,
         test_record_instance.init_record) = saved

    def test_the_default_raises_after_recording(self):
        self.assertIs(wrapper_failure_policy.raise_errors, True)
        with self.assertRaises(WebDriverException):
            webdriver_wrapper_instance.to_url("https://nowhere.test/")
        self.assertIn("ERR_NAME_NOT_RESOLVED", test_record_instance.test_record_list[-1]["program_exception"])

    def test_turned_off_the_call_returns_and_still_records(self):
        executor.set_raise_wrapper_errors(False)
        webdriver_wrapper_instance.to_url("https://nowhere.test/")
        self.assertIn("ERR_NAME_NOT_RESOLVED", test_record_instance.test_record_list[-1]["program_exception"])

    def test_actions_fail_by_default_including_a_wrong_assertion(self):
        element = MagicMock()
        element.get_attribute.return_value = "Sign out"
        element.text = "Sign out"
        element.tag_name = "button"
        web_element_wrapper.current_web_element = element
        record, failed = executor.collect_action_results([
            ["WR_to_url", {"url": "https://nowhere.test/"}],
            ["WR_element_assert", {"check_dict": {"tag_name": "a"}}],
        ])
        self.assertEqual(len(failed), 2)
        self.assertIn("ERR_NAME_NOT_RESOLVED", record[failed[0]])

    def test_an_action_file_can_turn_it_off(self):
        _record, failed = executor.collect_action_results([
            ["WR_set_raise_wrapper_errors", [False]],
            ["WR_to_url", {"url": "https://nowhere.test/"}],
        ])
        self.assertEqual(failed, [])


if __name__ == "__main__":
    unittest.main()
