import unittest

from je_web_runner.utils.assert_value.result_check import check_value, check_values
from je_web_runner.utils.exception.exceptions import WebRunnerAssertException


class TestResultCheck(unittest.TestCase):

    def test_check_value_pass(self):
        result_dict = {"title": "Hello", "url": "https://example.com"}
        check_value("title", "Hello", result_dict)

    def test_check_value_fail_raises(self):
        result_dict = {"title": "Hello"}
        with self.assertRaises(WebRunnerAssertException):
            check_value("title", "Wrong", result_dict)

    def test_check_value_missing_key_raises(self):
        result_dict = {"title": "Hello"}
        with self.assertRaises(WebRunnerAssertException):
            check_value("nonexistent", "value", result_dict)

    def test_check_values_pass(self):
        check_dict = {"a": 1, "b": 2}
        result_dict = {"a": 1, "b": 2}
        check_values(check_dict, result_dict)

    def test_check_values_fail_raises(self):
        check_dict = {"a": 1, "b": 999}
        result_dict = {"a": 1, "b": 2}
        with self.assertRaises(WebRunnerAssertException):
            check_values(check_dict, result_dict)


if __name__ == "__main__":
    unittest.main()
