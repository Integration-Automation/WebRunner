import unittest
from unittest.mock import MagicMock, patch

from je_web_runner.element.web_element_wrapper import web_element_wrapper
from je_web_runner.utils.self_healing.healing_locator import (
    HealingError,
    clear_fallbacks,
    find_with_healing_playwright,
    find_with_healing_selenium,
    healing_registry,
    register_fallback,
    register_fallbacks,
)
from je_web_runner.utils.test_object.test_object_record.test_object_record_class import (
    test_object_record,
)


class TestRegistry(unittest.TestCase):

    def setUp(self):
        clear_fallbacks()
        test_object_record.clean_record()

    def test_register_and_get(self):
        register_fallback("submit", "ID", "submit-btn")
        self.assertEqual(healing_registry.get("submit"), [("ID", "submit-btn")])

    def test_register_fallbacks_replaces_list(self):
        register_fallback("submit", "ID", "submit-btn")
        register_fallbacks("submit", [["NAME", "go"], ["XPATH", "//button"]])
        self.assertEqual(healing_registry.get("submit"), [("NAME", "go"), ("XPATH", "//button")])

    def test_clear_fallbacks(self):
        register_fallback("submit", "ID", "x")
        clear_fallbacks()
        self.assertEqual(healing_registry.get("submit"), [])


class TestSelfHealingSelenium(unittest.TestCase):

    def setUp(self):
        clear_fallbacks()
        test_object_record.clean_record()
        web_element_wrapper.current_web_element = None

    def test_no_candidates_raises(self):
        with patch(
            "je_web_runner.utils.self_healing.healing_locator.webdriver_wrapper_instance"
        ) as wrapper:
            wrapper.current_webdriver = MagicMock()
            with self.assertRaises(HealingError):
                find_with_healing_selenium("nope")

    def test_no_driver_raises(self):
        with patch(
            "je_web_runner.utils.self_healing.healing_locator.webdriver_wrapper_instance"
        ) as wrapper:
            wrapper.current_webdriver = None
            with self.assertRaises(HealingError):
                find_with_healing_selenium("submit")

    def test_primary_match_short_circuits(self):
        test_object_record.save_test_object("submit", "ID")
        with patch(
            "je_web_runner.utils.self_healing.healing_locator.webdriver_wrapper_instance"
        ) as wrapper:
            driver = MagicMock()
            wrapper.current_webdriver = driver
            driver.find_element.return_value = "primary-elem"
            result = find_with_healing_selenium("submit")
            self.assertEqual(result, "primary-elem")
            self.assertEqual(driver.find_element.call_count, 1)

    def test_falls_back_when_primary_misses(self):
        test_object_record.save_test_object("submit", "ID")
        register_fallback("submit", "NAME", "go")
        with patch(
            "je_web_runner.utils.self_healing.healing_locator.webdriver_wrapper_instance"
        ) as wrapper:
            driver = MagicMock()
            wrapper.current_webdriver = driver
            driver.find_element.side_effect = [RuntimeError("miss"), "fallback-elem"]
            result = find_with_healing_selenium("submit")
            self.assertEqual(result, "fallback-elem")
            self.assertEqual(driver.find_element.call_count, 2)

    def test_all_misses_raises_healing_error(self):
        test_object_record.save_test_object("submit", "ID")
        register_fallback("submit", "NAME", "go")
        with patch(
            "je_web_runner.utils.self_healing.healing_locator.webdriver_wrapper_instance"
        ) as wrapper:
            driver = MagicMock()
            wrapper.current_webdriver = driver
            driver.find_element.side_effect = RuntimeError("miss")
            with self.assertRaises(HealingError):
                find_with_healing_selenium("submit")


class TestSelfHealingPlaywright(unittest.TestCase):

    def setUp(self):
        clear_fallbacks()
        test_object_record.clean_record()

    def test_primary_then_fallback(self):
        test_object_record.save_test_object("login", "ID")
        register_fallback("login", "CSS_SELECTOR", "form input[type=submit]")
        with patch(
            "je_web_runner.utils.self_healing.healing_locator.playwright_wrapper_instance"
        ) as wrapper:
            page = MagicMock()
            wrapper.page = page
            page.query_selector.side_effect = [None, "match"]
            result = find_with_healing_playwright("login")
            self.assertEqual(result, "match")
            self.assertEqual(page.query_selector.call_count, 2)


if __name__ == "__main__":
    unittest.main()
