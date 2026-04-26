import unittest

from je_web_runner.utils.test_object.test_object_class import TestObject
from je_web_runner.utils.test_object.test_object_record.test_object_record_class import (
    test_object_record,
)
from je_web_runner.webdriver.playwright_locator import (
    PlaywrightLocatorError,
    selector_for_recorded_name,
)
from je_web_runner.webdriver.playwright_locator import (
    test_object_to_selector as _to_selector,
)


class TestPlaywrightLocator(unittest.TestCase):

    def setUp(self):
        test_object_record.clean_record()

    def test_css_selector_pass_through(self):
        obj = TestObject("button.primary", "CSS_SELECTOR")
        self.assertEqual(_to_selector(obj), "button.primary")

    def test_xpath_prefix(self):
        obj = TestObject("//button[@id='go']", "XPATH")
        self.assertEqual(_to_selector(obj), "xpath=//button[@id='go']")

    def test_id_strategy(self):
        obj = TestObject("submit", "ID")
        self.assertEqual(_to_selector(obj), "#submit")

    def test_name_strategy(self):
        obj = TestObject("q", "NAME")
        self.assertEqual(_to_selector(obj), "[name=\"q\"]")

    def test_class_name_strategy(self):
        obj = TestObject("primary", "CLASS_NAME")
        self.assertEqual(_to_selector(obj), ".primary")

    def test_tag_name_strategy(self):
        obj = TestObject("input", "TAG_NAME")
        self.assertEqual(_to_selector(obj), "input")

    def test_link_text_strategy(self):
        obj = TestObject("Sign in", "LINK_TEXT")
        self.assertEqual(_to_selector(obj), "text=Sign in")

    def test_partial_link_text_strategy(self):
        obj = TestObject("Sign", "PARTIAL_LINK_TEXT")
        self.assertEqual(_to_selector(obj), ":has-text(\"Sign\")")

    def test_unknown_strategy_raises(self):
        obj = TestObject.__new__(TestObject)
        obj.test_object_name = "x"
        obj.test_object_type = "QUACK"
        with self.assertRaises(PlaywrightLocatorError):
            _to_selector(obj)

    def test_selector_for_recorded_name_round_trip(self):
        test_object_record.save_test_object("login", "ID")
        self.assertEqual(selector_for_recorded_name("login"), "#login")

    def test_recorded_name_missing_raises(self):
        with self.assertRaises(PlaywrightLocatorError):
            selector_for_recorded_name("absent")


if __name__ == "__main__":
    unittest.main()
