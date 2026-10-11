"""Playwright frame scope, role/text lookup and dialog policy (progress #19, third batch)."""
import unittest
from unittest.mock import MagicMock, patch

from je_web_runner.utils.executor.action_executor import executor
from je_web_runner.webdriver import playwright_wrapper as pw_module
from je_web_runner.webdriver.playwright_wrapper import PlaywrightBackendError, PlaywrightWrapper


def _launch():
    page = MagicMock()
    page.url = "about:blank"
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


def _frame_under(parent, selector):
    frame = MagicMock()
    frame.parent_frame = parent
    iframe = MagicMock()
    iframe.content_frame.return_value = frame
    parent.query_selector.side_effect = lambda s: iframe if s == selector else None
    return frame


class TestFrameScope(unittest.TestCase):

    def test_selector_commands_act_in_the_selected_frame(self):
        wrapper, _context, page = _launch()
        frame = _frame_under(page, "#payment")
        frame.parent_frame = page.main_frame
        wrapper.switch_to_frame("#payment")
        wrapper.click("#pay")
        wrapper.fill("#card", "4242")
        wrapper.wait_for_selector("#done")
        frame.click.assert_called_once_with("#pay")
        frame.fill.assert_called_once_with("#card", "4242")
        frame.wait_for_selector.assert_called_once()
        page.click.assert_not_called()

    def test_nested_frames_parent_and_main(self):
        wrapper, _context, page = _launch()
        outer = _frame_under(page, "#outer")
        outer.parent_frame = page.main_frame
        inner = _frame_under(outer, "#inner")
        wrapper.switch_to_frame(["#outer", "#inner"])
        wrapper.click("#x")
        inner.click.assert_called_once_with("#x")
        wrapper.switch_to_parent_frame()
        wrapper.click("#y")
        outer.click.assert_called_once_with("#y")
        wrapper.switch_to_parent_frame()
        wrapper.click("#z")
        page.click.assert_called_once_with("#z")

    def test_navigation_returns_to_the_page(self):
        wrapper, _context, page = _launch()
        _frame_under(page, "#f")
        wrapper.switch_to_frame("#f")
        wrapper.to_url("https://example.com")
        wrapper.click("#a")
        page.click.assert_called_once_with("#a")

    def test_unknown_frame_raises(self):
        wrapper, _context, page = _launch()
        page.query_selector.return_value = None
        with self.assertRaises(PlaywrightBackendError):
            wrapper.switch_to_frame("#missing")


class TestFindBy(unittest.TestCase):

    def test_role_lookup_sets_the_current_element(self):
        wrapper, _context, page = _launch()
        handle = MagicMock()
        page.get_by_role.return_value.element_handles.return_value = [handle]
        self.assertIs(wrapper.find_by("role", "button", name="Pay"), handle)
        page.get_by_role.assert_called_once_with("button", name="Pay")
        page.get_by_role.return_value.first.wait_for.assert_called_once_with(state="attached")
        self.assertIs(wrapper.element_wrapper.current_element, handle)

    def test_unknown_lookup_raises(self):
        wrapper, _context, _page = _launch()
        with self.assertRaises(PlaywrightBackendError):
            wrapper.find_by("xpath", "//a")


class TestDialogs(unittest.TestCase):

    def _dialog(self, kind="prompt"):
        dialog = MagicMock()
        dialog.type, dialog.message, dialog.default_value = kind, "Name?", ""
        return dialog

    def test_accept_with_prompt_text_and_remember_the_dialog(self):
        wrapper, _context, page = _launch()
        wrapper.set_dialog_policy("accept", prompt_text="Ann")
        handler = next(call.args[1] for call in page.on.call_args_list if call.args[0] == "dialog")
        dialog = self._dialog()
        handler(dialog)
        dialog.accept.assert_called_once_with("Ann")
        self.assertEqual(wrapper.last_dialog()["message"], "Name?")

    def test_dismiss_and_pages_opened_later_follow_the_policy(self):
        wrapper, context, page = _launch()
        wrapper.set_dialog_policy("dismiss")
        popup = MagicMock()
        wrapper._track_page(popup)  # pylint: disable=protected-access — what context.on("page") calls
        handler = next(call.args[1] for call in popup.on.call_args_list if call.args[0] == "dialog")
        dialog = self._dialog("confirm")
        handler(dialog)
        dialog.dismiss.assert_called_once_with()
        self.assertEqual(sum(1 for call in page.on.call_args_list if call.args[0] == "dialog"), 1)

    def test_bad_action_raises(self):
        wrapper, _context, _page = _launch()
        with self.assertRaises(PlaywrightBackendError):
            wrapper.set_dialog_policy("ignore")


class TestCommands(unittest.TestCase):

    def test_commands_are_registered(self):
        for name in ("WR_pw_switch_to_frame", "WR_pw_switch_to_parent_frame", "WR_pw_switch_to_main_frame",
                     "WR_pw_find_by", "WR_pw_set_dialog_policy", "WR_pw_last_dialog"):
            self.assertIn(name, executor.event_dict)


if __name__ == "__main__":
    unittest.main()
