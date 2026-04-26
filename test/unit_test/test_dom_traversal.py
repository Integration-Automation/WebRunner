import unittest
from unittest.mock import MagicMock, patch

from je_web_runner.utils.dom_traversal.shadow_iframe import (
    DOMTraversalError,
    playwright_frame_locator_chain,
    playwright_query_in_shadow,
    playwright_shadow_selector,
    selenium_back_to_default,
    selenium_query_in_shadow,
    selenium_switch_iframe_chain,
)


class TestShadowQuerySelenium(unittest.TestCase):

    def test_no_driver_raises(self):
        with patch("je_web_runner.utils.dom_traversal.shadow_iframe.webdriver_wrapper_instance") as wrapper:
            wrapper.current_webdriver = None
            with self.assertRaises(DOMTraversalError):
                selenium_query_in_shadow(["my-app"], "button")

    def test_dispatches_with_chain_and_inner(self):
        with patch("je_web_runner.utils.dom_traversal.shadow_iframe.webdriver_wrapper_instance") as wrapper:
            driver = MagicMock()
            wrapper.current_webdriver = driver
            driver.execute_script.return_value = "elem"
            result = selenium_query_in_shadow(["my-app", "my-button"], "button.primary")
            self.assertEqual(result, "elem")
            args = driver.execute_script.call_args[0]
            self.assertEqual(args[1], ["my-app", "my-button"])
            self.assertEqual(args[2], "button.primary")


class TestShadowQueryPlaywright(unittest.TestCase):

    def test_pierce_selector_format(self):
        selector = playwright_shadow_selector(["my-app", "my-button"], "button")
        self.assertEqual(selector, "my-app >>> my-button >>> button")

    def test_query_in_shadow_dispatches_via_query_selector(self):
        with patch("je_web_runner.utils.dom_traversal.shadow_iframe.playwright_wrapper_instance") as wrapper:
            page = MagicMock()
            wrapper.page = page
            page.query_selector.return_value = "elem"
            self.assertEqual(playwright_query_in_shadow(["my-app"], "button"), "elem")
            page.query_selector.assert_called_once_with("my-app >>> button")


class TestIframeSelenium(unittest.TestCase):

    def test_switch_chain_visits_each(self):
        with patch("je_web_runner.utils.dom_traversal.shadow_iframe.webdriver_wrapper_instance") as wrapper:
            driver = MagicMock()
            wrapper.current_webdriver = driver
            selenium_switch_iframe_chain(["#outer", "#inner"])
            driver.switch_to.default_content.assert_called_once()
            self.assertEqual(driver.find_element.call_count, 2)
            self.assertEqual(driver.switch_to.frame.call_count, 2)

    def test_back_to_default_calls_switch(self):
        with patch("je_web_runner.utils.dom_traversal.shadow_iframe.webdriver_wrapper_instance") as wrapper:
            driver = MagicMock()
            wrapper.current_webdriver = driver
            selenium_back_to_default()
            driver.switch_to.default_content.assert_called_once()


class TestIframePlaywright(unittest.TestCase):

    def test_chain_calls_frame_locator_per_selector(self):
        with patch("je_web_runner.utils.dom_traversal.shadow_iframe.playwright_wrapper_instance") as wrapper:
            page = MagicMock()
            wrapper.page = page
            outer = MagicMock()
            inner = MagicMock()
            page.frame_locator.return_value = outer
            outer.frame_locator.return_value = inner
            result = playwright_frame_locator_chain(["#outer", "#inner"])
            self.assertIs(result, inner)
            page.frame_locator.assert_called_with("#outer")
            outer.frame_locator.assert_called_with("#inner")


if __name__ == "__main__":
    unittest.main()
