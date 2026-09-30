"""
Playwright 同步 backend 包裝器，與既有 Selenium 路徑並行。
Playwright sync backend wrapper running side-by-side with the Selenium path.
It covers most everyday operations of ``WebDriverWrapper`` but is not a
one-to-one copy; ``docs/source/Eng/doc/backends/backends_doc.rst`` lists the
equivalent commands and what exists on one backend only.

設計原則 / Design notes:
- ``playwright`` 為軟相依，未安裝時呼叫才會丟出含安裝提示的錯誤。
  Playwright is a soft dependency; the import error only surfaces on first use.
- 不改寫 Selenium 的 ``WebDriverWrapper``；本 backend 完全獨立，使用 ``WR_pw_*``
  命名空間。
  Selenium ``WebDriverWrapper`` is untouched; this backend lives entirely under
  the ``WR_pw_*`` namespace and shares no mutable state with it.
- 元素層操作沿用「找完先存、後續對當前元素操作」流程，與既有 element wrapper
  一致；亦提供 page-level 直接快捷（``pw_click(selector)`` 等）。
"""
from __future__ import annotations

from typing import Any

from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.utils.test_object.test_object_record.test_object_record_class import (
    test_object_record,
)
from je_web_runner.webdriver._playwright_mixins import (
    _ContextMixin,
    _InteractionMixin,
    _PageMixin,
    _RecordingMixin,
    _StateMixin,
)
from je_web_runner.webdriver._playwright_mixins._common import (
    BROWSER_NOT_LAUNCHED,
    PlaywrightBackendError,
)
from je_web_runner.webdriver.playwright_element_wrapper import (
    PlaywrightElementWrapper,
    playwright_element_wrapper,
)
from je_web_runner.webdriver.playwright_locator import test_object_to_selector


def _require_playwright():
    """Import Playwright lazily; surface a clear install hint when missing."""
    try:
        from playwright.sync_api import sync_playwright  # type: ignore[import-not-found]
        return sync_playwright
    except ImportError as error:
        raise PlaywrightBackendError(
            "Playwright is not installed. Install with: "
            "pip install playwright && python -m playwright install"
        ) from error


_SUPPORTED_BROWSERS = frozenset({"chromium", "firefox", "webkit"})


class PlaywrightWrapper(
    _ContextMixin,
    _PageMixin,
    _InteractionMixin,
    _StateMixin,
    _RecordingMixin,
):
    """
    Playwright 同步 API 的完整 backend 包裝
    Full sync-API wrapper for Playwright, organised around one browser /
    one context / multiple pages.
    """

    def __init__(self, element_wrapper: PlaywrightElementWrapper | None = None) -> None:
        self._playwright = None
        self._browser = None
        self._context = None
        self._pages: list[Any] = []
        self._page_index: int = -1
        # The merged options every new context gets (see _ContextMixin), and which
        # of them came from the current device descriptor.
        self._context_options: dict[str, Any] = {}
        self._emulation_keys: set[str] = set()
        # Tracing options while a trace is being recorded (see _RecordingMixin), else None.
        self._trace_options: dict[str, Any] | None = None
        # Init scripts and URL blocks, re-applied to every rebuilt context.
        self._init_scripts: list[str] = []
        self._blocked_urls: list[Any] = []
        self.element_wrapper = element_wrapper or playwright_element_wrapper

    # ----- lifecycle ---------------------------------------------------

    @property
    def page(self):
        if not self._pages or self._page_index < 0:
            raise PlaywrightBackendError("Playwright page not launched; call launch() first")
        return self._pages[self._page_index]

    @property
    def context(self):
        if self._context is None:
            raise PlaywrightBackendError("Playwright context not started; call launch() first")
        return self._context

    @property
    def browser(self):
        if self._browser is None:
            raise PlaywrightBackendError(BROWSER_NOT_LAUNCHED)
        return self._browser

    def launch(
        self,
        browser: str = "chromium",
        headless: bool = True,
        record_har_path: str | None = None,
        record_har_content: str = "omit",
        context_options: dict[str, Any] | None = None,
        **launch_options: Any,
    ) -> None:
        """
        啟動指定瀏覽器；可選擇於 context 開啟 HAR 錄製
        Launch the requested browser. ``context_options`` go to every context this
        wrapper creates (``user_agent``, ``viewport``, ``locale``, ``storage_state``,
        ``record_video_dir`` …); ``record_har_path`` starts HAR recording, with
        ``record_har_content`` ``"omit"`` / ``"embed"`` / ``"attach"``. Other keyword
        arguments go to ``browser_type.launch``.
        """
        web_runner_logger.info(f"playwright launch: browser={browser}, headless={headless}")
        if browser not in _SUPPORTED_BROWSERS:
            raise PlaywrightBackendError(
                f"unsupported playwright browser: {browser!r}; "
                f"choose one of {sorted(_SUPPORTED_BROWSERS)}"
            )
        sync_playwright = _require_playwright()
        self._playwright = sync_playwright().start()
        browser_type = getattr(self._playwright, browser)
        self._browser = browser_type.launch(headless=headless, **launch_options)
        self._context_options = dict(context_options or {})
        self._emulation_keys = set()
        if record_har_path:
            self._context_options.update({"record_har_path": record_har_path, "record_har_content": record_har_content})
        self._context = self._open_context()
        page = self._context.new_page()
        self._pages = [page]
        self._page_index = 0

    def _open_context(self, storage_state: Any = None):
        """Create a context with the merged options (plus ``storage_state`` carried from the last one)."""
        kwargs = dict(self._context_options)
        if storage_state is not None:
            kwargs["storage_state"] = storage_state
        context = self._browser.new_context(**kwargs)
        context.on("page", self._track_page)
        self._reapply_context_setup(context)
        self._restart_tracing(context)
        return context

    def quit(self) -> None:
        """Close everything and stop the Playwright runtime."""
        web_runner_logger.info("playwright quit")
        try:
            if self._browser is not None:
                self._browser.close()
        finally:
            self._pages = []
            self._page_index = -1
            self._context = None
            self._browser = None
            self._context_options = {}
            self._emulation_keys = set()
            self._trace_options = None
            self._init_scripts = []
            self._blocked_urls = []
            if self._playwright is not None:
                self._playwright.stop()
            self._playwright = None


playwright_wrapper_instance = PlaywrightWrapper()


# ----- module-level shortcuts (executor binding) ----------------------

def pw_launch(browser: str = "chromium", headless: bool = True, **options: Any) -> None:
    playwright_wrapper_instance.launch(browser=browser, headless=headless, **options)


def pw_start_har_recording(har_path: str, content: str = "omit") -> None:
    playwright_wrapper_instance.start_har_recording(har_path, content=content)


def pw_stop_har_recording() -> None:
    playwright_wrapper_instance.stop_har_recording()


def pw_route_mock(url_pattern: str, response: dict) -> None:
    playwright_wrapper_instance.route_mock(url_pattern, response)


def pw_route_mock_json(url_pattern: str, json_data: Any, status: int = 200) -> None:
    playwright_wrapper_instance.route_mock_json(url_pattern, json_data, status=status)


def pw_route_unmock(url_pattern: str) -> None:
    playwright_wrapper_instance.route_unmock(url_pattern)


def pw_route_clear() -> None:
    playwright_wrapper_instance.route_clear()


def pw_emulate(device_name: str) -> None:
    playwright_wrapper_instance.start_emulation(device_name)


def pw_stop_emulate() -> None:
    playwright_wrapper_instance.stop_emulation()


def pw_list_devices() -> list[str]:
    return playwright_wrapper_instance.list_device_names()


def pw_set_geolocation(latitude: float, longitude: float, accuracy: float | None = None) -> None:
    playwright_wrapper_instance.set_geolocation(latitude, longitude, accuracy=accuracy)


def pw_grant_permissions(permissions: list[str], origin: str | None = None) -> None:
    playwright_wrapper_instance.grant_permissions(permissions, origin=origin)


def pw_clear_permissions() -> None:
    playwright_wrapper_instance.clear_permissions()


def pw_set_timezone(timezone_id: str) -> None:
    playwright_wrapper_instance.set_timezone(timezone_id)


def pw_clock_install(fake_now_ms: float | None = None) -> None:
    playwright_wrapper_instance.clock_install(fake_now_ms)


def pw_clock_set_time(time_ms: float) -> None:
    playwright_wrapper_instance.clock_set_time(time_ms)


def pw_clock_run_for(duration_ms: float) -> None:
    playwright_wrapper_instance.clock_run_for(duration_ms)


def pw_set_locale(locale: str, accept_language: str | None = None) -> None:
    playwright_wrapper_instance.set_locale(locale, accept_language=accept_language)


def pw_set_context_options(**options: Any) -> None:
    playwright_wrapper_instance.set_context_options(**options)


def pw_set_user_agent(user_agent: str) -> None:
    playwright_wrapper_instance.set_user_agent(user_agent)


def pw_set_extra_http_headers(headers: dict[str, str]) -> None:
    playwright_wrapper_instance.set_extra_http_headers(headers)


def pw_save_storage_state(path: str) -> str:
    return playwright_wrapper_instance.save_storage_state(path)


def pw_tracing_start(screenshots: bool = True, snapshots: bool = True, sources: bool = False) -> None:
    playwright_wrapper_instance.start_tracing(screenshots=screenshots, snapshots=snapshots, sources=sources)


def pw_tracing_save_chunk(path: str) -> str:
    return playwright_wrapper_instance.save_trace_chunk(path)


def pw_tracing_stop(path: str) -> str:
    return playwright_wrapper_instance.stop_tracing(path)


def pw_video_start(video_dir: str, width: int | None = None, height: int | None = None) -> None:
    playwright_wrapper_instance.start_video_recording(video_dir, width=width, height=height)


def pw_video_stop() -> list[str]:
    return playwright_wrapper_instance.stop_video_recording()


def pw_add_init_script(source: str) -> None:
    playwright_wrapper_instance.add_init_script(source)


def pw_block_urls(patterns: list[str]) -> None:
    playwright_wrapper_instance.block_urls(patterns)


def pw_unblock_urls() -> None:
    playwright_wrapper_instance.unblock_urls()


def pw_clear_geolocation() -> None:
    playwright_wrapper_instance.clear_geolocation()


def pw_bring_to_front() -> None:
    playwright_wrapper_instance.bring_to_front()


def pw_switch_to_page_by_url(pattern: str) -> bool:
    return playwright_wrapper_instance.switch_to_page_by_url(pattern)


def pw_switch_to_page_by_title(pattern: str) -> bool:
    return playwright_wrapper_instance.switch_to_page_by_title(pattern)


def pw_screenshot_base64(full_page: bool = False) -> str:
    return playwright_wrapper_instance.screenshot_base64(full_page=full_page)


def pw_print_page(file_path: str) -> str:
    return playwright_wrapper_instance.print_page(file_path)


def pw_scroll(scroll_x: float, scroll_y: float) -> None:
    playwright_wrapper_instance.scroll(scroll_x, scroll_y)


def pw_scroll_to_top() -> None:
    playwright_wrapper_instance.scroll_to_top()


def pw_scroll_to_bottom() -> None:
    playwright_wrapper_instance.scroll_to_bottom()


def pw_drag_and_drop_offset(selector: str, target_x: float, target_y: float) -> None:
    playwright_wrapper_instance.drag_and_drop_offset(selector, target_x, target_y)


def pw_get_cookie(name: str) -> dict | None:
    return playwright_wrapper_instance.get_cookie(name)


def pw_delete_cookie(name: str) -> None:
    playwright_wrapper_instance.delete_cookie(name)


def pw_check_current_page(check_dict: dict) -> None:
    playwright_wrapper_instance.check_current_page(check_dict)


def pw_quit() -> None:
    playwright_wrapper_instance.quit()


def pw_to_url(url: str, **goto_options: Any) -> None:
    playwright_wrapper_instance.to_url(url, **goto_options)


def pw_forward() -> None:
    playwright_wrapper_instance.forward()


def pw_back() -> None:
    playwright_wrapper_instance.back()


def pw_refresh() -> None:
    playwright_wrapper_instance.refresh()


def pw_url() -> str:
    return playwright_wrapper_instance.url()


def pw_title() -> str:
    return playwright_wrapper_instance.title()


def pw_content() -> str:
    return playwright_wrapper_instance.content()


def pw_set_default_timeout(timeout_ms: float) -> None:
    playwright_wrapper_instance.set_default_timeout(timeout_ms)


def pw_set_default_navigation_timeout(timeout_ms: float) -> None:
    playwright_wrapper_instance.set_default_navigation_timeout(timeout_ms)


def pw_new_page() -> int:
    return playwright_wrapper_instance.new_page()


def pw_switch_to_page(index: int) -> None:
    playwright_wrapper_instance.switch_to_page(index)


def pw_close_page(index: int | None = None) -> None:
    playwright_wrapper_instance.close_page(index)


def pw_page_count() -> int:
    return playwright_wrapper_instance.page_count()


def pw_find_element(selector: str):
    return playwright_wrapper_instance.find_element(selector)


def pw_find_elements(selector: str) -> list[Any]:
    return playwright_wrapper_instance.find_elements(selector)


def pw_find_element_with_test_object_record(element_name: str):
    return playwright_wrapper_instance.find_element_with_test_object_record(element_name)


def pw_find_elements_with_test_object_record(element_name: str):
    return playwright_wrapper_instance.find_elements_with_test_object_record(element_name)


def pw_click(selector: str, **options: Any) -> None:
    playwright_wrapper_instance.click(selector, **options)


def pw_dblclick(selector: str, **options: Any) -> None:
    playwright_wrapper_instance.dblclick(selector, **options)


def pw_hover(selector: str, **options: Any) -> None:
    playwright_wrapper_instance.hover(selector, **options)


def pw_fill(selector: str, value: str, **options: Any) -> None:
    playwright_wrapper_instance.fill(selector, value, **options)


def pw_type_text(selector: str, value: str, delay: float = 0, **options: Any) -> None:
    playwright_wrapper_instance.type_text(selector, value, delay=delay, **options)


def pw_press(selector: str, key: str, **options: Any) -> None:
    playwright_wrapper_instance.press(selector, key, **options)


def pw_check(selector: str, **options: Any) -> None:
    playwright_wrapper_instance.check(selector, **options)


def pw_uncheck(selector: str, **options: Any) -> None:
    playwright_wrapper_instance.uncheck(selector, **options)


def pw_select_option(selector: str, value: Any, **options: Any) -> list[str]:
    return playwright_wrapper_instance.select_option(selector, value, **options)


def pw_drag_and_drop(source_selector: str, target_selector: str, **options: Any) -> None:
    playwright_wrapper_instance.drag_and_drop(source_selector, target_selector, **options)


def pw_evaluate(expression: str, arg: Any = None):
    return playwright_wrapper_instance.evaluate(expression, arg)


def pw_get_cookies() -> list[dict]:
    return playwright_wrapper_instance.get_cookies()


def pw_add_cookies(cookies: list[dict]) -> None:
    playwright_wrapper_instance.add_cookies(cookies)


def pw_clear_cookies() -> None:
    playwright_wrapper_instance.clear_cookies()


def pw_screenshot(path: str, full_page: bool = False) -> str:
    return playwright_wrapper_instance.screenshot(path, full_page=full_page)


def pw_screenshot_bytes(full_page: bool = False) -> bytes:
    return playwright_wrapper_instance.screenshot_bytes(full_page=full_page)


def pw_wait_for_selector(selector: str, timeout: float | None = None, state: str = "visible"):
    return playwright_wrapper_instance.wait_for_selector(selector, timeout=timeout, state=state)


def pw_wait_for_load_state(state: str = "load", timeout: float | None = None) -> None:
    playwright_wrapper_instance.wait_for_load_state(state, timeout=timeout)


def pw_wait_for_timeout(timeout_ms: float) -> None:
    playwright_wrapper_instance.wait_for_timeout(timeout_ms)


def pw_wait_for_url(url: str, timeout: float | None = None) -> None:
    playwright_wrapper_instance.wait_for_url(url, timeout=timeout)


def pw_set_viewport_size(width: int, height: int) -> None:
    playwright_wrapper_instance.set_viewport_size(width, height)


def pw_viewport_size() -> dict | None:
    return playwright_wrapper_instance.viewport_size()


def pw_mouse_click(x: float, y: float, button: str = "left", click_count: int = 1) -> None:
    playwright_wrapper_instance.mouse_click(x, y, button=button, click_count=click_count)


def pw_mouse_move(x: float, y: float, steps: int = 1) -> None:
    playwright_wrapper_instance.mouse_move(x, y, steps=steps)


def pw_mouse_down(button: str = "left", click_count: int = 1) -> None:
    playwright_wrapper_instance.mouse_down(button=button, click_count=click_count)


def pw_mouse_up(button: str = "left", click_count: int = 1) -> None:
    playwright_wrapper_instance.mouse_up(button=button, click_count=click_count)


def pw_keyboard_press(key: str) -> None:
    playwright_wrapper_instance.keyboard_press(key)


def pw_keyboard_type(text: str, delay: float = 0) -> None:
    playwright_wrapper_instance.keyboard_type(text, delay=delay)


def pw_keyboard_down(key: str) -> None:
    playwright_wrapper_instance.keyboard_down(key)


def pw_keyboard_up(key: str) -> None:
    playwright_wrapper_instance.keyboard_up(key)


def pw_save_test_object_to_selector(test_object_name: str, object_type: str = "CSS_SELECTOR") -> str:
    """
    把 TestObject 存進 ``test_object_record`` 並回傳對應的 Playwright selector
    Save a TestObject under ``test_object_record`` and return its Playwright
    selector. Convenience for scripts that want to register and use a locator
    in one step.
    """
    test_object_record.save_test_object(test_object_name, object_type)
    return test_object_to_selector(test_object_record.test_object_record_dict[test_object_name])
