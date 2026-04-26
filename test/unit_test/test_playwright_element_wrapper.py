import os
import tempfile
import unittest
from unittest.mock import MagicMock

from je_web_runner.webdriver.playwright_element_wrapper import (
    PlaywrightElementError,
    PlaywrightElementWrapper,
)


class TestPlaywrightElementWrapper(unittest.TestCase):

    def setUp(self):
        self.element = MagicMock()
        self.wrapper = PlaywrightElementWrapper()
        self.wrapper.current_element = self.element

    def test_no_current_element_raises_internally(self):
        wrapper = PlaywrightElementWrapper()
        with self.assertRaises(PlaywrightElementError):
            wrapper._require_element()

    def test_click_dblclick_hover(self):
        self.wrapper.click()
        self.element.click.assert_called_once()
        self.wrapper.dblclick()
        self.element.dblclick.assert_called_once()
        self.wrapper.hover()
        self.element.hover.assert_called_once()

    def test_fill_clears_via_empty_string(self):
        self.wrapper.fill("hello")
        self.element.fill.assert_called_once_with("hello")
        self.wrapper.clear()
        self.element.fill.assert_called_with("")

    def test_type_text_passes_delay(self):
        self.wrapper.type_text("abc", delay=15)
        self.element.type.assert_called_once_with("abc", delay=15)

    def test_press_passes_key(self):
        self.wrapper.press("Enter")
        self.element.press.assert_called_once_with("Enter")

    def test_check_uncheck_select_option(self):
        self.wrapper.check()
        self.element.check.assert_called_once()
        self.wrapper.uncheck()
        self.element.uncheck.assert_called_once()
        self.element.select_option.return_value = ["v"]
        self.assertEqual(self.wrapper.select_option("v"), ["v"])

    def test_get_attribute_and_property(self):
        self.element.get_attribute.return_value = "btn"
        self.assertEqual(self.wrapper.get_attribute("class"), "btn")
        prop_handle = MagicMock()
        prop_handle.json_value.return_value = 7
        self.element.get_property.return_value = prop_handle
        self.assertEqual(self.wrapper.get_property("tabIndex"), 7)

    def test_inner_text_html_visibility(self):
        self.element.inner_text.return_value = "hi"
        self.element.inner_html.return_value = "<b>hi</b>"
        self.element.is_visible.return_value = True
        self.element.is_enabled.return_value = True
        self.element.is_checked.return_value = False
        self.assertEqual(self.wrapper.inner_text(), "hi")
        self.assertEqual(self.wrapper.inner_html(), "<b>hi</b>")
        self.assertTrue(self.wrapper.is_visible())
        self.assertTrue(self.wrapper.is_enabled())
        self.assertFalse(self.wrapper.is_checked())

    def test_scroll_into_view_calls_helper(self):
        self.wrapper.scroll_into_view()
        self.element.scroll_into_view_if_needed.assert_called_once()

    def test_screenshot_appends_png(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = os.path.join(tmpdir, "shot")
            target = self.wrapper.screenshot(base)
            self.assertEqual(target, base + ".png")
            self.element.screenshot.assert_called_once_with(path=base + ".png")

    def test_change_element_swaps_current(self):
        first = MagicMock()
        second = MagicMock()
        self.wrapper.current_element_list = [first, second]
        self.wrapper.change_element(1)
        self.assertIs(self.wrapper.current_element, second)

    def test_change_element_without_list_records_error(self):
        wrapper = PlaywrightElementWrapper()
        wrapper.change_element(0)  # should not raise; recorded as failure
        self.assertIsNone(wrapper.current_element)

    def test_swallowed_errors_do_not_leak(self):
        self.element.click.side_effect = RuntimeError("boom")
        # Should not raise — error path is logged + recorded.
        self.wrapper.click()


if __name__ == "__main__":
    unittest.main()
