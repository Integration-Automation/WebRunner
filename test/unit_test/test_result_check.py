import types
import unittest

from je_web_runner.utils.assert_value.result_check import (
    check_value,
    check_values,
    check_web_element_details,
    check_web_element_value,
    check_webdriver_details,
    check_webdriver_value,
)
from je_web_runner.utils.exception.exceptions import WebRunnerAssertException


def _fake_webdriver(**overrides):
    attrs = {
        "mobile": "mobile-obj",
        "name": "chrome",
        "title": "Example",
        "current_url": "https://example.com",
        "page_source": "<html></html>",
        "current_window_handle": "win-1",
        "window_handles": ["win-1"],
        "switch_to": "switch-obj",
        "timeouts": "timeouts-obj",
        "capabilities": {"browserName": "chrome"},
        "file_detector": "detector-obj",
        "application_cache": None,
        "virtual_authenticator_id": None,
    }
    attrs.update(overrides)
    return types.SimpleNamespace(**attrs)


def _fake_web_element(**overrides):
    attrs = {
        "tag_name": "div",
        "text": "hello",
        "location_once_scrolled_into_view": {"x": 0, "y": 0},
        "size": {"width": 10, "height": 20},
        "location": {"x": 1, "y": 2},
        "parent": "parent-obj",
        "id": "el-1",
    }
    attrs.update(overrides)
    return types.SimpleNamespace(**attrs)


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


class TestResultCheckMessageDirection(unittest.TestCase):
    """Lock in the 'should be <expected> but value was <actual>' direction."""

    def test_check_value_message_direction(self):
        # third arg is the ACTUAL dict, second arg is the EXPECTED value
        with self.assertRaises(WebRunnerAssertException) as ctx:
            check_value("title", "Expected", {"title": "Actual"})
        message = str(ctx.exception)
        self.assertIn("should be Expected", message)
        self.assertIn("was Actual", message)

    def test_check_values_message_direction(self):
        # check_dict = ACTUAL, result_check_dict = EXPECTED (as the detail
        # checkers call it); message must read should be <expected> was <actual>
        with self.assertRaises(WebRunnerAssertException) as ctx:
            check_values({"k": "Actual"}, {"k": "Expected"})
        message = str(ctx.exception)
        self.assertIn("should be Expected", message)
        self.assertIn("was Actual", message)


class TestWebDriverDetailCheck(unittest.TestCase):

    def test_check_webdriver_value_pass(self):
        check_webdriver_value("name", "chrome", _fake_webdriver())

    def test_check_webdriver_value_fail(self):
        with self.assertRaises(WebRunnerAssertException):
            check_webdriver_value("name", "firefox", _fake_webdriver())

    def test_check_webdriver_details_pass(self):
        check_webdriver_details(
            _fake_webdriver(),
            {"title": "Example", "current_url": "https://example.com"},
        )

    def test_check_webdriver_details_fail(self):
        with self.assertRaises(WebRunnerAssertException):
            check_webdriver_details(_fake_webdriver(), {"title": "Nope"})


class TestWebElementDetailCheck(unittest.TestCase):

    def test_check_web_element_value_pass(self):
        check_web_element_value("tag_name", "div", _fake_web_element())

    def test_check_web_element_value_fail(self):
        with self.assertRaises(WebRunnerAssertException):
            check_web_element_value("tag_name", "span", _fake_web_element())

    def test_check_web_element_details_pass(self):
        check_web_element_details(
            _fake_web_element(), {"tag_name": "div", "text": "hello"}
        )

    def test_check_web_element_details_fail(self):
        with self.assertRaises(WebRunnerAssertException):
            check_web_element_details(_fake_web_element(), {"text": "wrong"})


if __name__ == "__main__":
    unittest.main()
