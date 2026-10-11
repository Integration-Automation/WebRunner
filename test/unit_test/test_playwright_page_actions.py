"""Page-level Playwright actions: option pass-through, report records, popup tracking."""
import unittest
from unittest.mock import MagicMock, patch

from je_web_runner.utils.test_record.test_record_class import test_record_instance
from je_web_runner.webdriver import playwright_wrapper as pw_module
from je_web_runner.webdriver.playwright_wrapper import PlaywrightWrapper


def _launch_with_fakes():
    page = MagicMock()
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
        wrapper.launch(browser="chromium", headless=True)
    return wrapper, context, page


def _handler(mock_obj, event):
    """Return the callback registered with ``mock_obj.on(event, callback)``."""
    for call in mock_obj.on.call_args_list:
        if call.args and call.args[0] == event:
            return call.args[1]
    raise AssertionError(f"no {event!r} handler registered")


class TestModuleFunctionsForwardOptions(unittest.TestCase):

    def test_selector_shortcuts_pass_playwright_options_through(self):
        instance = MagicMock()
        with patch.object(pw_module, "playwright_wrapper_instance", instance):
            pw_module.pw_click("#a", button="right", modifiers=["Shift"])
            pw_module.pw_dblclick("#a", delay=5)
            pw_module.pw_hover("#a", force=True)
            pw_module.pw_fill("#a", "v", timeout=100)
            pw_module.pw_type_text("#a", "v", delay=1, timeout=100)
            pw_module.pw_press("#a", "Enter", delay=10)
            pw_module.pw_check("#a", force=True)
            pw_module.pw_uncheck("#a", force=True)
            pw_module.pw_select_option("#a", "x", timeout=100)
            pw_module.pw_drag_and_drop("#a", "#b", target_position={"x": 1, "y": 2})
            pw_module.pw_to_url("https://example.com", wait_until="networkidle")
        instance.click.assert_called_once_with("#a", button="right", modifiers=["Shift"])
        instance.dblclick.assert_called_once_with("#a", delay=5)
        instance.hover.assert_called_once_with("#a", force=True)
        instance.fill.assert_called_once_with("#a", "v", timeout=100)
        instance.type_text.assert_called_once_with("#a", "v", delay=1, timeout=100)
        instance.press.assert_called_once_with("#a", "Enter", delay=10)
        instance.check.assert_called_once_with("#a", force=True)
        instance.uncheck.assert_called_once_with("#a", force=True)
        instance.select_option.assert_called_once_with("#a", "x", timeout=100)
        instance.drag_and_drop.assert_called_once_with("#a", "#b", target_position={"x": 1, "y": 2})
        instance.to_url.assert_called_once_with("https://example.com", wait_until="networkidle")

    def test_wrapper_methods_hand_options_to_the_page(self):
        wrapper, _, page = _launch_with_fakes()
        wrapper.press("#a", "Enter", delay=10)
        wrapper.check("#c", force=True)
        wrapper.uncheck("#c", trial=True)
        wrapper.type_text("#t", "hi", delay=1, timeout=50)
        wrapper.select_option("#s", "x", timeout=50)
        page.press.assert_called_once_with("#a", "Enter", delay=10)
        page.check.assert_called_once_with("#c", force=True)
        page.uncheck.assert_called_once_with("#c", trial=True)
        page.type.assert_called_once_with("#t", "hi", delay=1, timeout=50)
        page.select_option.assert_called_once_with("#s", "x", timeout=50)


class TestPageActionsAreRecorded(unittest.TestCase):

    def setUp(self):
        self._was_enabled = test_record_instance.init_record
        test_record_instance.set_record_enable(True)
        test_record_instance.clean_record()
        self.addCleanup(test_record_instance.set_record_enable, self._was_enabled)
        self.addCleanup(test_record_instance.clean_record)

    def _names(self):
        return [entry["function_name"] for entry in test_record_instance.test_record_list]

    def test_successful_actions_are_recorded_with_their_params(self):
        wrapper, _, _ = _launch_with_fakes()
        wrapper.click("#go", button="right")
        wrapper.back()
        wrapper.wait_for_selector("#done")
        self.assertEqual(self._names(), ["Playwright click", "Playwright back", "Playwright wait_for_selector"])
        first = test_record_instance.test_record_list[0]
        self.assertEqual(first["local_param"], {"selector": "#go", "options": {"button": "right"}})
        self.assertEqual(first["program_exception"], "None")

    def test_a_failing_action_is_recorded_and_still_raises(self):
        wrapper, _, page = _launch_with_fakes()
        page.click.side_effect = RuntimeError("detached")
        with self.assertRaises(RuntimeError):
            wrapper.click("#gone")
        entry = test_record_instance.test_record_list[-1]
        self.assertEqual(entry["function_name"], "Playwright click")
        self.assertIn("detached", entry["program_exception"])

    def test_cookie_values_stay_out_of_the_record(self):
        wrapper, _, _ = _launch_with_fakes()
        wrapper.add_cookies([{"name": "session", "value": "secret", "url": "https://x"}])
        entry = test_record_instance.test_record_list[-1]
        self.assertEqual(entry["function_name"], "Playwright add_cookies")
        self.assertNotIn("secret", repr(entry["local_param"]))


class TestPopupTracking(unittest.TestCase):

    def test_pages_opened_by_the_site_are_tracked(self):
        wrapper, context, first = _launch_with_fakes()
        popup = MagicMock()
        _handler(context, "page")(popup)
        self.assertEqual(wrapper.page_count(), 2)
        wrapper.switch_to_page(1)
        self.assertIs(wrapper.page, popup)

    def test_a_page_that_closes_itself_is_forgotten(self):
        wrapper, context, first = _launch_with_fakes()
        popup = MagicMock()
        _handler(context, "page")(popup)
        wrapper.switch_to_page(1)
        _handler(popup, "close")(popup)
        self.assertEqual(wrapper.page_count(), 1)
        self.assertIs(wrapper.page, first)

    def test_new_page_is_not_counted_twice_when_the_event_fires(self):
        wrapper, context, _ = _launch_with_fakes()
        second = MagicMock()

        def open_page():
            _handler(context, "page")(second)  # Playwright fires "page" for context.new_page() too
            return second

        context.new_page.side_effect = open_page
        self.assertEqual(wrapper.new_page(), 1)
        self.assertEqual(wrapper.page_count(), 2)

    def test_close_page_removes_exactly_one_page_when_the_close_event_fires(self):
        wrapper, context, first = _launch_with_fakes()
        second = MagicMock()
        context.new_page.return_value = second
        wrapper.new_page()
        second.close.side_effect = lambda: _handler(second, "close")(second)
        wrapper.close_page(1)
        self.assertEqual(wrapper.page_count(), 1)
        self.assertIs(wrapper.page, first)


if __name__ == "__main__":
    unittest.main()
