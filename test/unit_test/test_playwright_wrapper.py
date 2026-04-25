import sys
import unittest
from unittest.mock import MagicMock, patch

from je_web_runner.utils.test_object.test_object_record.test_object_record_class import (
    test_object_record,
)
from je_web_runner.webdriver import playwright_wrapper as pw_module
from je_web_runner.webdriver.playwright_wrapper import (
    PlaywrightBackendError,
    PlaywrightWrapper,
)


def _build_fake_playwright():
    page = MagicMock()
    context = MagicMock()
    context.new_page.return_value = page
    browser = MagicMock()
    browser.new_context.return_value = context
    chromium = MagicMock()
    chromium.launch.return_value = browser
    firefox = MagicMock()
    firefox.launch.return_value = browser
    webkit = MagicMock()
    webkit.launch.return_value = browser
    playwright = MagicMock(chromium=chromium, firefox=firefox, webkit=webkit)
    factory = MagicMock()
    factory_callable = MagicMock(return_value=factory)
    factory.start.return_value = playwright
    return factory_callable, playwright, browser, context, page


def _launch_with_fakes():
    factory_callable, playwright, browser, context, page = _build_fake_playwright()
    with patch.object(pw_module, "_require_playwright", return_value=factory_callable):
        wrapper = PlaywrightWrapper()
        wrapper.launch(browser="chromium", headless=True)
    return wrapper, playwright, browser, context, page


class TestLifecycle(unittest.TestCase):

    def test_page_property_raises_before_launch(self):
        wrapper = PlaywrightWrapper()
        with self.assertRaises(PlaywrightBackendError):
            _ = wrapper.page

    def test_unsupported_browser_rejected(self):
        wrapper = PlaywrightWrapper()
        with self.assertRaises(PlaywrightBackendError):
            wrapper.launch(browser="ie")

    def test_launch_then_quit_resets_state(self):
        wrapper, playwright, browser, _, _ = _launch_with_fakes()
        wrapper.quit()
        browser.close.assert_called_once()
        playwright.stop.assert_called_once()
        with self.assertRaises(PlaywrightBackendError):
            _ = wrapper.page

    def test_missing_playwright_raises_helpful_error(self):
        with patch.dict(sys.modules, {"playwright": None, "playwright.sync_api": None}):
            wrapper = PlaywrightWrapper()
            with self.assertRaises(PlaywrightBackendError) as context:
                wrapper.launch()
            self.assertIn("pip install playwright", str(context.exception))


class TestPagesNavigation(unittest.TestCase):

    def test_new_page_switch_close(self):
        wrapper, _, _, context, page1 = _launch_with_fakes()
        page2 = MagicMock()
        context.new_page.return_value = page2
        index = wrapper.new_page()
        self.assertEqual(index, 1)
        self.assertIs(wrapper.page, page2)
        wrapper.switch_to_page(0)
        self.assertIs(wrapper.page, page1)
        wrapper.close_page(1)
        self.assertEqual(wrapper.page_count(), 1)

    def test_switch_to_invalid_page_raises(self):
        wrapper, *_ = _launch_with_fakes()
        with self.assertRaises(PlaywrightBackendError):
            wrapper.switch_to_page(5)

    def test_navigation_calls_page_methods(self):
        wrapper, _, _, _, page = _launch_with_fakes()
        wrapper.to_url("https://example.com")
        page.goto.assert_called_once_with("https://example.com")
        wrapper.forward()
        page.go_forward.assert_called_once()
        wrapper.back()
        page.go_back.assert_called_once()
        wrapper.refresh()
        page.reload.assert_called_once()

    def test_url_title_content_pass_through(self):
        wrapper, _, _, _, page = _launch_with_fakes()
        page.url = "u"
        page.title.return_value = "t"
        page.content.return_value = "<html/>"
        self.assertEqual(wrapper.url(), "u")
        self.assertEqual(wrapper.title(), "t")
        self.assertEqual(wrapper.content(), "<html/>")

    def test_default_timeouts_propagate(self):
        wrapper, _, _, _, page = _launch_with_fakes()
        wrapper.set_default_timeout(1000)
        page.set_default_timeout.assert_called_once_with(1000)
        wrapper.set_default_navigation_timeout(2000)
        page.set_default_navigation_timeout.assert_called_once_with(2000)


class TestFinding(unittest.TestCase):

    def setUp(self):
        test_object_record.clean_record()

    def test_find_element_and_elements(self):
        wrapper, _, _, _, page = _launch_with_fakes()
        page.query_selector.return_value = "elem"
        page.query_selector_all.return_value = ["a", "b"]
        self.assertEqual(wrapper.find_element("#x"), "elem")
        self.assertEqual(wrapper.find_elements(".y"), ["a", "b"])

    def test_find_with_test_object_record_updates_element_wrapper(self):
        wrapper, _, _, _, page = _launch_with_fakes()
        page.query_selector.return_value = "single"
        page.query_selector_all.return_value = ["one", "two"]
        test_object_record.save_test_object("submit", "ID")
        wrapper.find_element_with_test_object_record("submit")
        self.assertEqual(wrapper.element_wrapper.current_element, "single")
        page.query_selector.assert_called_with("#submit")

        wrapper.find_elements_with_test_object_record("submit")
        self.assertEqual(wrapper.element_wrapper.current_element_list, ["one", "two"])
        self.assertEqual(wrapper.element_wrapper.current_element, "one")


class TestPageShortcuts(unittest.TestCase):

    def test_click_fill_and_friends(self):
        wrapper, _, _, _, page = _launch_with_fakes()
        wrapper.click("#go")
        page.click.assert_called_once_with("#go")
        wrapper.dblclick("#go")
        page.dblclick.assert_called_once()
        wrapper.hover("#go")
        page.hover.assert_called_once()
        wrapper.fill("#input", "hi")
        page.fill.assert_called_once_with("#input", "hi")
        wrapper.type_text("#input", "hi", delay=10)
        page.type.assert_called_once_with("#input", "hi", delay=10)
        wrapper.press("#input", "Enter")
        page.press.assert_called_once_with("#input", "Enter")
        wrapper.check("#cb")
        page.check.assert_called_once()
        wrapper.uncheck("#cb")
        page.uncheck.assert_called_once()

    def test_select_and_drag(self):
        wrapper, _, _, _, page = _launch_with_fakes()
        page.select_option.return_value = ["a"]
        self.assertEqual(wrapper.select_option("#sel", "a"), ["a"])
        wrapper.drag_and_drop("#src", "#dst")
        page.drag_and_drop.assert_called_once_with("#src", "#dst")


class TestCookiesAndScript(unittest.TestCase):

    def test_cookies_and_evaluate(self):
        wrapper, _, _, context, page = _launch_with_fakes()
        context.cookies.return_value = [{"name": "k"}]
        self.assertEqual(wrapper.get_cookies(), [{"name": "k"}])
        wrapper.add_cookies([{"name": "x", "value": "v", "url": "https://e"}])
        context.add_cookies.assert_called_once()
        wrapper.clear_cookies()
        context.clear_cookies.assert_called_once()

        page.evaluate.return_value = 7
        self.assertEqual(wrapper.evaluate("1 + 1"), 7)
        wrapper.evaluate("x => x", 5)
        page.evaluate.assert_called_with("x => x", 5)


class TestWaitsAndViewport(unittest.TestCase):

    def test_waits_and_viewport(self):
        wrapper, _, _, _, page = _launch_with_fakes()
        wrapper.wait_for_selector("#x")
        page.wait_for_selector.assert_called_with("#x", state="visible")
        wrapper.wait_for_selector("#x", timeout=500)
        page.wait_for_selector.assert_called_with("#x", timeout=500, state="visible")
        wrapper.wait_for_load_state()
        page.wait_for_load_state.assert_called_with("load")
        wrapper.wait_for_timeout(50)
        page.wait_for_timeout.assert_called_with(50)
        wrapper.wait_for_url("/home")
        page.wait_for_url.assert_called_with("/home")

        wrapper.set_viewport_size(1024, 768)
        page.set_viewport_size.assert_called_once_with({"width": 1024, "height": 768})
        page.viewport_size = {"width": 1024, "height": 768}
        self.assertEqual(wrapper.viewport_size(), {"width": 1024, "height": 768})


class TestMouseAndKeyboard(unittest.TestCase):

    def test_mouse_and_keyboard_dispatch(self):
        wrapper, _, _, _, page = _launch_with_fakes()
        wrapper.mouse_click(10, 20)
        page.mouse.click.assert_called_once_with(10, 20, button="left", click_count=1)
        wrapper.mouse_move(30, 40, steps=5)
        page.mouse.move.assert_called_once_with(30, 40, steps=5)
        wrapper.mouse_down()
        wrapper.mouse_up()
        page.mouse.down.assert_called_once()
        page.mouse.up.assert_called_once()

        wrapper.keyboard_press("Enter")
        page.keyboard.press.assert_called_once_with("Enter")
        wrapper.keyboard_type("hello", delay=5)
        page.keyboard.type.assert_called_once_with("hello", delay=5)
        wrapper.keyboard_down("Shift")
        wrapper.keyboard_up("Shift")
        page.keyboard.down.assert_called_with("Shift")
        page.keyboard.up.assert_called_with("Shift")


class TestHarRecording(unittest.TestCase):

    def test_launch_with_har_path_passes_to_new_context(self):
        factory_callable, playwright, browser, _, _ = _build_fake_playwright()
        with patch.object(pw_module, "_require_playwright", return_value=factory_callable):
            wrapper = PlaywrightWrapper()
            wrapper.launch(record_har_path="run.har", record_har_content="embed")
        browser.new_context.assert_called_once_with(
            record_har_path="run.har", record_har_content="embed"
        )

    def test_start_stop_har_recording_swaps_context(self):
        wrapper, _, browser, original_context, _ = _launch_with_fakes()
        new_context = MagicMock()
        new_context.new_page.return_value = MagicMock()
        browser.new_context.return_value = new_context
        wrapper.start_har_recording("run.har")
        original_context.close.assert_called_once()
        # Each call to new_context replaces the wrapped instance.
        self.assertIs(wrapper.context, new_context)
        wrapper.stop_har_recording()
        new_context.close.assert_called_once()

    def test_start_har_without_browser_raises(self):
        wrapper = PlaywrightWrapper()
        with self.assertRaises(PlaywrightBackendError):
            wrapper.start_har_recording("run.har")


class TestDeviceEmulation(unittest.TestCase):

    def _launch_with_devices(self, devices_dict):
        factory_callable, playwright, browser, context, _ = _build_fake_playwright()
        playwright.devices = devices_dict
        with patch.object(pw_module, "_require_playwright", return_value=factory_callable):
            wrapper = PlaywrightWrapper()
            wrapper.launch(browser="chromium", headless=True)
        return wrapper, browser, context

    def test_list_devices_returns_sorted_keys(self):
        wrapper, _, _ = self._launch_with_devices({"iPhone 13": {}, "Pixel 7": {}})
        self.assertEqual(wrapper.list_device_names(), ["Pixel 7", "iPhone 13"])

    def test_start_emulation_passes_device_options_to_new_context(self):
        wrapper, browser, original_context = self._launch_with_devices({
            "iPhone 13": {"viewport": {"width": 390, "height": 844}, "userAgent": "iphone"}
        })
        new_context = MagicMock()
        new_context.new_page.return_value = MagicMock()
        browser.new_context.return_value = new_context
        wrapper.start_emulation("iPhone 13")
        original_context.close.assert_called_once()
        kwargs = browser.new_context.call_args.kwargs
        self.assertEqual(kwargs["userAgent"], "iphone")
        self.assertEqual(kwargs["viewport"]["width"], 390)

    def test_unknown_device_raises(self):
        wrapper, _, _ = self._launch_with_devices({"iPhone 13": {}})
        with self.assertRaises(PlaywrightBackendError):
            wrapper.start_emulation("Nokia 3310")

    def test_stop_emulation_replaces_context(self):
        wrapper, browser, original_context = self._launch_with_devices({"iPhone 13": {}})
        new_context = MagicMock()
        new_context.new_page.return_value = MagicMock()
        browser.new_context.return_value = new_context
        wrapper.stop_emulation()
        original_context.close.assert_called_once()
        self.assertIs(wrapper.context, new_context)


class TestContextOverrides(unittest.TestCase):

    def test_set_geolocation_calls_context(self):
        wrapper, _, _, context, _ = _launch_with_fakes()
        wrapper.set_geolocation(35.0, 139.0, accuracy=10)
        context.set_geolocation.assert_called_once_with(
            {"latitude": 35.0, "longitude": 139.0, "accuracy": 10}
        )

    def test_grant_and_clear_permissions(self):
        wrapper, _, _, context, _ = _launch_with_fakes()
        wrapper.grant_permissions(["geolocation"])
        context.grant_permissions.assert_called_once_with(["geolocation"])
        wrapper.grant_permissions(["clipboard-read"], origin="https://e.com")
        context.grant_permissions.assert_called_with(["clipboard-read"], origin="https://e.com")
        wrapper.clear_permissions()
        context.clear_permissions.assert_called_once()

    def test_set_timezone_recreates_context(self):
        wrapper, _, browser, original_context, _ = _launch_with_fakes()
        new_context = MagicMock()
        new_context.new_page.return_value = MagicMock()
        browser.new_context.return_value = new_context
        wrapper.set_timezone("Asia/Tokyo")
        original_context.close.assert_called_once()
        kwargs = browser.new_context.call_args.kwargs
        self.assertEqual(kwargs["timezone_id"], "Asia/Tokyo")

    def test_clock_install_with_and_without_time(self):
        wrapper, _, _, context, _ = _launch_with_fakes()
        clock = MagicMock()
        context.clock = clock
        wrapper.clock_install()
        clock.install.assert_called_once_with()
        clock.install.reset_mock()
        wrapper.clock_install(123456789)
        clock.install.assert_called_once_with(time=123456789)

    def test_clock_set_and_run_for(self):
        wrapper, _, _, context, _ = _launch_with_fakes()
        clock = MagicMock()
        context.clock = clock
        wrapper.clock_set_time(1000)
        clock.set_fixed_time.assert_called_once_with(1000)
        wrapper.clock_run_for(500)
        clock.run_for.assert_called_once_with(500)

    def test_clock_unavailable_raises(self):
        wrapper, _, _, context, _ = _launch_with_fakes()
        context.clock = None
        with self.assertRaises(PlaywrightBackendError):
            wrapper.clock_install()

    def test_set_locale_recreates_context_with_options(self):
        wrapper, _, browser, original_context, _ = _launch_with_fakes()
        new_context = MagicMock()
        new_context.new_page.return_value = MagicMock()
        browser.new_context.return_value = new_context
        wrapper.set_locale("ja-JP", accept_language="ja,en;q=0.9")
        original_context.close.assert_called_once()
        kwargs = browser.new_context.call_args.kwargs
        self.assertEqual(kwargs["locale"], "ja-JP")
        self.assertEqual(kwargs["extra_http_headers"]["Accept-Language"], "ja,en;q=0.9")


class TestRouteMocking(unittest.TestCase):

    def test_route_mock_registers_handler(self):
        wrapper, _, _, _, page = _launch_with_fakes()
        wrapper.route_mock("**/api/users", {"status": 201, "body": "{}"})
        page.route.assert_called_once()
        pattern = page.route.call_args[0][0]
        handler = page.route.call_args[0][1]
        self.assertEqual(pattern, "**/api/users")

        # Simulate Playwright invoking the handler
        route_obj = MagicMock()
        request_obj = MagicMock()
        handler(route_obj, request_obj)
        kwargs = route_obj.fulfill.call_args.kwargs
        self.assertEqual(kwargs["status"], 201)
        self.assertEqual(kwargs["body"], "{}")

    def test_route_mock_json_serialises(self):
        wrapper, _, _, _, page = _launch_with_fakes()
        wrapper.route_mock_json("**/api", {"a": 1}, status=202)
        handler = page.route.call_args[0][1]
        route_obj = MagicMock()
        handler(route_obj, MagicMock())
        kwargs = route_obj.fulfill.call_args.kwargs
        self.assertEqual(kwargs["status"], 202)
        self.assertIn('"a": 1', kwargs["body"])
        self.assertEqual(kwargs["headers"]["Content-Type"], "application/json")

    def test_route_unmock_and_clear(self):
        wrapper, _, _, _, page = _launch_with_fakes()
        wrapper.route_unmock("**/api")
        page.unroute.assert_called_once_with("**/api")
        wrapper.route_clear()
        page.unroute_all.assert_called_once()


class TestScreenshots(unittest.TestCase):

    def test_screenshot_returns_path(self):
        wrapper, _, _, _, page = _launch_with_fakes()
        self.assertEqual(wrapper.screenshot("out.png"), "out.png")
        page.screenshot.assert_called_once_with(path="out.png", full_page=False)
        page.screenshot.reset_mock()
        page.screenshot.return_value = b"PNG"
        self.assertEqual(wrapper.screenshot_bytes(full_page=True), b"PNG")
        page.screenshot.assert_called_once_with(full_page=True)


if __name__ == "__main__":
    unittest.main()
