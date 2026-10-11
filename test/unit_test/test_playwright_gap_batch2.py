"""Playwright twins for per-name cookies, form submit, CSS values and assertions (progress #19, second batch)."""
import unittest
from unittest.mock import MagicMock, patch

from je_web_runner.utils.exception.exceptions import WebRunnerAssertException
from je_web_runner.utils.executor.action_executor import executor
from je_web_runner.webdriver import playwright_wrapper as pw_module
from je_web_runner.webdriver.playwright_element_wrapper import PlaywrightElementWrapper
from je_web_runner.webdriver.playwright_wrapper import PlaywrightWrapper


def _launch():
    page = MagicMock()
    page.url = "https://shop.example/cart"
    page.title.return_value = "Cart"
    page.viewport_size = {"width": 1280, "height": 720}
    context = MagicMock()
    context.new_page.return_value = page
    browser = MagicMock()
    browser.new_context.return_value = context
    playwright = MagicMock()
    playwright.chromium.launch.return_value = browser
    factory = MagicMock()
    factory.start.return_value = playwright
    with patch.object(pw_module, "_require_playwright", return_value=MagicMock(return_value=factory)):
        wrapper = PlaywrightWrapper()
        wrapper.launch(browser="chromium")
    return wrapper, context, page


class TestCookiesByName(unittest.TestCase):

    def test_get_and_delete_one_cookie(self):
        wrapper, context, _page = _launch()
        context.cookies.return_value = [{"name": "a", "value": "1"}, {"name": "sid", "value": "x"}]
        self.assertEqual(wrapper.get_cookie("sid"), {"name": "sid", "value": "x"})
        self.assertIsNone(wrapper.get_cookie("missing"))
        wrapper.delete_cookie("sid")
        context.clear_cookies.assert_called_once_with(name="sid")


class TestPageAssertion(unittest.TestCase):

    def test_matching_fields_pass(self):
        wrapper, _context, _page = _launch()
        wrapper.check_current_page({"title": "Cart", "current_url": "https://shop.example/cart"})

    def test_a_mismatch_raises(self):
        wrapper, _context, _page = _launch()
        with self.assertRaises(WebRunnerAssertException):
            wrapper.check_current_page({"title": "Checkout"})

    def test_an_unknown_field_raises(self):
        wrapper, _context, _page = _launch()
        with self.assertRaises(WebRunnerAssertException):
            wrapper.check_current_page({"mobile": True})


class TestElementCommands(unittest.TestCase):

    def setUp(self):
        self.wrapper = PlaywrightElementWrapper()
        self.element = MagicMock()
        self.wrapper.current_element = self.element

    def test_submit_runs_the_forms_request_submit(self):
        self.wrapper.submit()
        script = self.element.evaluate.call_args.args[0]
        self.assertIn("requestSubmit", script)

    def test_css_value(self):
        self.element.evaluate.return_value = "rgb(0, 0, 0)"
        self.assertEqual(self.wrapper.value_of_css_property("color"), "rgb(0, 0, 0)")
        self.assertEqual(self.element.evaluate.call_args.args[1], "color")

    def test_element_assertion(self):
        self.element.inner_text.return_value = "Pay now"
        self.element.is_visible.return_value = True
        self.element.evaluate.return_value = "button"
        self.wrapper.check_current_element({"text": "Pay now", "visible": True, "tag_name": "button"})
        with self.assertRaises(WebRunnerAssertException):
            self.wrapper.check_current_element({"text": "Cancel"})
        with self.assertRaises(WebRunnerAssertException):
            self.wrapper.check_current_element({"parent": "x"})

    def test_assertion_failure_fails_the_action(self):
        from je_web_runner.webdriver.playwright_element_wrapper import playwright_element_wrapper
        saved = playwright_element_wrapper.current_element
        self.addCleanup(setattr, playwright_element_wrapper, "current_element", saved)
        playwright_element_wrapper.current_element = MagicMock()
        playwright_element_wrapper.current_element.inner_text.return_value = "Pay now"
        _record, failed = executor.collect_action_results(
            [["WR_pw_element_assert", {"check_dict": {"text": "Cancel"}}]])
        self.assertEqual(len(failed), 1)


class TestCommands(unittest.TestCase):

    def test_commands_are_registered(self):
        for name in ("WR_pw_get_cookie", "WR_pw_delete_cookie", "WR_pw_check_current_page",
                     "WR_pw_element_submit", "WR_pw_element_value_of_css_property", "WR_pw_element_assert"):
            self.assertIn(name, executor.event_dict)


if __name__ == "__main__":
    unittest.main()
