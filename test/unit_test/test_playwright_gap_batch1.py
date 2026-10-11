"""Playwright commands matching Selenium ones that had no WR_pw_* twin (progress #19, first batch)."""
import base64
import re
import unittest
from unittest.mock import MagicMock, patch

from je_web_runner.utils.executor.action_executor import executor
from je_web_runner.webdriver import playwright_wrapper as pw_module
from je_web_runner.webdriver.playwright_wrapper import PlaywrightWrapper


def _launch():
    contexts = []

    def new_context(**_kwargs):
        context = MagicMock()
        page = MagicMock()
        page.url = "about:blank"
        context.new_page.return_value = page
        contexts.append(context)
        return context

    browser = MagicMock()
    browser.new_context.side_effect = new_context
    playwright = MagicMock()
    playwright.chromium.launch.return_value = browser
    factory = MagicMock()
    factory.start.return_value = playwright
    with patch.object(pw_module, "_require_playwright", return_value=MagicMock(return_value=factory)):
        wrapper = PlaywrightWrapper()
        wrapper.launch(browser="chromium")
    return wrapper, contexts


class TestInitScriptAndBlocking(unittest.TestCase):

    def test_init_script_is_added_and_survives_a_rebuild(self):
        wrapper, contexts = _launch()
        wrapper.add_init_script("window.__probe = 1;")
        contexts[0].add_init_script.assert_called_once_with("window.__probe = 1;")
        wrapper.set_timezone("UTC")
        contexts[1].add_init_script.assert_called_once_with("window.__probe = 1;")

    def test_init_script_is_behind_the_script_gate(self):
        original = executor.allow_arbitrary_script
        self.addCleanup(executor.set_allow_arbitrary_script, original)
        executor.set_allow_arbitrary_script(False)
        _record, failed = executor.collect_action_results([["WR_pw_add_init_script", {"source": "1"}]])
        self.assertEqual(len(failed), 1)

    def test_block_urls_uses_selenium_wildcards_and_survives_a_rebuild(self):
        wrapper, contexts = _launch()
        wrapper.block_urls(["*.doubleclick.net/*"])
        pattern, handler = contexts[0].route.call_args.args
        self.assertIsInstance(pattern, re.Pattern)
        self.assertTrue(pattern.match("https://ad.doubleclick.net/x/y.js"))
        self.assertFalse(pattern.match("https://example.com/"))
        route = MagicMock()
        handler(route)
        route.abort.assert_called_once_with()
        wrapper.set_locale("en-US")
        self.assertEqual(contexts[1].route.call_count, 1)
        wrapper.unblock_urls()
        contexts[1].unroute.assert_called_once()
        wrapper.set_locale("fr-FR")
        contexts[2].route.assert_not_called()


class TestPageCommands(unittest.TestCase):

    def test_geolocation_clear_bring_to_front_pdf_and_base64(self):
        wrapper, _contexts = _launch()
        wrapper.clear_geolocation()
        wrapper.context.set_geolocation.assert_called_once_with(None)
        wrapper.bring_to_front()
        wrapper.page.bring_to_front.assert_called_once_with()
        self.assertEqual(wrapper.print_page("out.pdf"), "out.pdf")
        wrapper.page.pdf.assert_called_once_with(path="out.pdf")
        wrapper.page.screenshot.return_value = b"\x89PNG"
        self.assertEqual(wrapper.screenshot_base64(), base64.b64encode(b"\x89PNG").decode("ascii"))

    def test_scrolling(self):
        wrapper, _contexts = _launch()
        wrapper.scroll(0, 400)
        wrapper.page.mouse.wheel.assert_called_once_with(0, 400)
        wrapper.scroll_to_top()
        wrapper.page.evaluate.assert_called_with("window.scrollTo(0, 0)")
        wrapper.scroll_to_bottom()
        wrapper.page.evaluate.assert_called_with("window.scrollTo(0, document.body.scrollHeight)")

    def test_drag_by_offset_moves_the_mouse_from_the_element_centre(self):
        wrapper, _contexts = _launch()
        wrapper.page.locator.return_value.bounding_box.return_value = {"x": 10, "y": 20, "width": 100, "height": 40}
        wrapper.drag_and_drop_offset("#slider", 50, 0)
        mouse = wrapper.page.mouse
        mouse.move.assert_any_call(60.0, 40.0)
        mouse.down.assert_called_once_with()
        mouse.move.assert_any_call(110.0, 40.0, steps=5)
        mouse.up.assert_called_once_with()

    def test_switch_page_by_url_and_title(self):
        wrapper, contexts = _launch()
        second = MagicMock()
        second.url = "https://shop.example/checkout"
        second.title.return_value = "Checkout"
        contexts[0].new_page.return_value = second
        wrapper.new_page()
        wrapper.switch_to_page(0)
        self.assertTrue(wrapper.switch_to_page_by_url("/checkout"))
        self.assertIs(wrapper.page, second)
        wrapper.switch_to_page(0)
        self.assertTrue(wrapper.switch_to_page_by_title("Check"))
        self.assertIs(wrapper.page, second)
        self.assertFalse(wrapper.switch_to_page_by_title("nope"))


class TestCommands(unittest.TestCase):

    def test_commands_are_registered(self):
        for name in ("WR_pw_add_init_script", "WR_pw_block_urls", "WR_pw_unblock_urls", "WR_pw_clear_geolocation",
                     "WR_pw_bring_to_front", "WR_pw_print_page", "WR_pw_screenshot_base64", "WR_pw_scroll",
                     "WR_pw_scroll_to_top", "WR_pw_scroll_to_bottom", "WR_pw_drag_and_drop_offset",
                     "WR_pw_switch_to_page_by_url", "WR_pw_switch_to_page_by_title"):
            self.assertIn(name, executor.event_dict)


if __name__ == "__main__":
    unittest.main()
