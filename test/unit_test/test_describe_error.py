"""``describe_error``: one line that always carries the message, for records and failure text."""
import unittest
from unittest.mock import MagicMock

from selenium.common.exceptions import NoSuchElementException, WebDriverException

from je_web_runner.utils.exception.exceptions import describe_error
from je_web_runner.utils.executor.action_executor import Executor
from je_web_runner.utils.test_record.test_record_class import record_action_to_list, test_record_instance


class TestDescribeError(unittest.TestCase):

    def test_selenium_errors_keep_their_message(self):
        # repr() of a Selenium exception is just "WebDriverException()".
        self.assertEqual(describe_error(WebDriverException("net::ERR_NAME_NOT_RESOLVED")),
                         "WebDriverException('net::ERR_NAME_NOT_RESOLVED')")
        self.assertTrue(describe_error(NoSuchElementException("no #x")).startswith("NoSuchElementException('no #x"))

    def test_everything_else_is_repr(self):
        self.assertEqual(describe_error(None), "None")
        self.assertEqual(describe_error(ValueError("bad")), "ValueError('bad')")
        self.assertEqual(describe_error(WebDriverException()), "WebDriverException()")
        self.assertEqual(describe_error(RuntimeError()), "RuntimeError()")

    def test_the_test_record_and_the_action_record_use_it(self):
        self.addCleanup(setattr, test_record_instance, "test_record_list", test_record_instance.test_record_list)
        self.addCleanup(setattr, test_record_instance, "init_record", test_record_instance.init_record)
        test_record_instance.test_record_list = []
        test_record_instance.set_record_enable(True)
        record_action_to_list("to_url", {}, WebDriverException("timeout"))
        self.assertEqual(test_record_instance.test_record_list[0]["program_exception"],
                         "WebDriverException('timeout')")
        runner = Executor()
        runner.event_dict["WR_probe"] = MagicMock(side_effect=WebDriverException("no such window"))
        record, failed = runner.collect_action_results([["WR_probe"]])
        self.assertEqual(record[failed[0]], "WebDriverException('no such window')")


if __name__ == "__main__":
    unittest.main()
