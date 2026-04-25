"""
Playwright 同步 backend 完整版包裝器，與既有 Selenium 路徑並行。
Full Playwright sync backend wrapper running side-by-side with the Selenium
path. Mirrors the operational surface of ``WebDriverWrapper`` where it makes
sense in Playwright (some Selenium-only concepts such as IE options or
webdriver_manager bootstrap intentionally do not exist here).

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

from typing import Any, Dict, List, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.utils.test_object.test_object_record.test_object_record_class import (
    test_object_record,
)
from je_web_runner.utils.test_record.test_record_class import record_action_to_list
from je_web_runner.webdriver.playwright_element_wrapper import (
    PlaywrightElementWrapper,
    playwright_element_wrapper,
)
from je_web_runner.webdriver.playwright_locator import (
    selector_for_recorded_name,
    test_object_to_selector,
)


class PlaywrightBackendError(WebRunnerException):
    """Raised when the Playwright backend is misused or unavailable."""


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

_BROWSER_NOT_LAUNCHED = "Playwright browser not launched; call launch() first"
_RUNTIME_NOT_STARTED = "Playwright runtime not started"
_CLOCK_API_UNAVAILABLE = "Playwright clock API unavailable; upgrade Playwright"


def _record(name: str, params, error: Optional[Exception]) -> None:
    record_action_to_list(f"Playwright {name}", params, error)


class PlaywrightWrapper:
    """
    Playwright 同步 API 的完整 backend 包裝
    Full sync-API wrapper for Playwright, organised around one browser /
    one context / multiple pages.
    """

    def __init__(self, element_wrapper: Optional[PlaywrightElementWrapper] = None) -> None:
        self._playwright = None
        self._browser = None
        self._context = None
        self._pages: List[Any] = []
        self._page_index: int = -1
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
            raise PlaywrightBackendError(_BROWSER_NOT_LAUNCHED)
        return self._browser

    def launch(
        self,
        browser: str = "chromium",
        headless: bool = True,
        record_har_path: Optional[str] = None,
        record_har_content: str = "omit",
        **launch_options: Any,
    ) -> None:
        """
        啟動指定瀏覽器；可選擇於 context 開啟 HAR 錄製
        Launch the requested browser; optionally enable HAR recording on the
        context. ``record_har_content`` accepts ``"omit"`` / ``"embed"`` /
        ``"attach"`` (Playwright defaults).
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
        self._context = self._build_context(record_har_path, record_har_content)
        page = self._context.new_page()
        self._pages = [page]
        self._page_index = 0

    def _build_context(
        self,
        record_har_path: Optional[str] = None,
        record_har_content: str = "omit",
        extra_options: Optional[dict] = None,
    ):
        """Create a context, optionally configured with HAR recording / extras."""
        kwargs = dict(extra_options or {})
        if record_har_path:
            kwargs["record_har_path"] = record_har_path
            kwargs["record_har_content"] = record_har_content
        return self._browser.new_context(**kwargs) if kwargs else self._browser.new_context()

    def _device_options(self, device_name: str) -> dict:
        """Look up Playwright's built-in device descriptor by name."""
        if self._playwright is None:
            raise PlaywrightBackendError(_RUNTIME_NOT_STARTED)
        devices = getattr(self._playwright, "devices", None)
        if not devices or device_name not in devices:
            available = sorted(devices.keys()) if devices else []
            raise PlaywrightBackendError(
                f"unknown device {device_name!r}; available examples: {available[:5]}"
            )
        return dict(devices[device_name])

    def start_emulation(self, device_name: str) -> None:
        """
        套用 Playwright 內建裝置設定（重建 context 與 page）
        Apply a Playwright device descriptor by name; the current context is
        closed and replaced with one configured for the requested device.
        """
        web_runner_logger.info(f"playwright start_emulation: {device_name}")
        if self._browser is None:
            raise PlaywrightBackendError(_BROWSER_NOT_LAUNCHED)
        if self._context is not None:
            self._context.close()
        self._context = self._build_context(extra_options=self._device_options(device_name))
        page = self._context.new_page()
        self._pages = [page]
        self._page_index = 0

    def stop_emulation(self) -> None:
        """Replace the device-emulating context with a plain one."""
        web_runner_logger.info("playwright stop_emulation")
        if self._browser is None:
            raise PlaywrightBackendError(_BROWSER_NOT_LAUNCHED)
        if self._context is not None:
            self._context.close()
        self._context = self._build_context()
        page = self._context.new_page()
        self._pages = [page]
        self._page_index = 0

    # ----- geolocation / permissions / timezone / clock --------------

    def set_geolocation(
        self,
        latitude: float,
        longitude: float,
        accuracy: Optional[float] = None,
    ) -> None:
        """Set the page geolocation; remember to grant ``geolocation`` permission first."""
        web_runner_logger.info(f"playwright set_geolocation: {latitude}, {longitude}")
        coords: Dict[str, float] = {"latitude": latitude, "longitude": longitude}
        if accuracy is not None:
            coords["accuracy"] = accuracy
        self.context.set_geolocation(coords)

    def grant_permissions(
        self,
        permissions: List[str],
        origin: Optional[str] = None,
    ) -> None:
        """Grant browser permissions (e.g. ``geolocation`` / ``clipboard-read``)."""
        if origin is None:
            self.context.grant_permissions(permissions)
        else:
            self.context.grant_permissions(permissions, origin=origin)

    def clear_permissions(self) -> None:
        self.context.clear_permissions()

    def set_timezone(self, timezone_id: str) -> None:
        """
        重建 context 並指定時區（Playwright 不支援直接修改既有 context 的時區）
        Recreate the context with ``timezoneId``; the existing page is closed.
        """
        web_runner_logger.info(f"playwright set_timezone: {timezone_id}")
        if self._browser is None:
            raise PlaywrightBackendError(_BROWSER_NOT_LAUNCHED)
        if self._context is not None:
            self._context.close()
        self._context = self._build_context(extra_options={"timezone_id": timezone_id})
        page = self._context.new_page()
        self._pages = [page]
        self._page_index = 0

    def clock_install(self, fake_now_ms: Optional[float] = None) -> None:
        """Install Playwright's clock (requires Playwright 1.45+)."""
        clock = getattr(self.context, "clock", None)
        if clock is None:
            raise PlaywrightBackendError(_CLOCK_API_UNAVAILABLE)
        if fake_now_ms is None:
            clock.install()
        else:
            clock.install(time=fake_now_ms)

    def clock_set_time(self, time_ms: float) -> None:
        clock = getattr(self.context, "clock", None)
        if clock is None:
            raise PlaywrightBackendError(_CLOCK_API_UNAVAILABLE)
        clock.set_fixed_time(time_ms)

    def clock_run_for(self, duration_ms: float) -> None:
        clock = getattr(self.context, "clock", None)
        if clock is None:
            raise PlaywrightBackendError(_CLOCK_API_UNAVAILABLE)
        clock.run_for(duration_ms)

    def set_locale(
        self,
        locale: str,
        accept_language: Optional[str] = None,
    ) -> None:
        """
        切換 ``locale`` 與 ``Accept-Language``（重建 context）
        Recreate the context with the given ``locale`` (and optional
        Accept-Language override). The current page is closed.
        """
        web_runner_logger.info(f"playwright set_locale: {locale}")
        if self._browser is None:
            raise PlaywrightBackendError(_BROWSER_NOT_LAUNCHED)
        options: Dict[str, Any] = {"locale": locale}
        if accept_language:
            options["extra_http_headers"] = {"Accept-Language": accept_language}
        if self._context is not None:
            self._context.close()
        self._context = self._build_context(extra_options=options)
        page = self._context.new_page()
        self._pages = [page]
        self._page_index = 0

    def list_device_names(self) -> List[str]:
        """Return all device names known to the active Playwright runtime."""
        if self._playwright is None:
            raise PlaywrightBackendError(_RUNTIME_NOT_STARTED)
        devices = getattr(self._playwright, "devices", None) or {}
        return sorted(devices.keys())

    def start_har_recording(self, har_path: str, content: str = "omit") -> None:
        """
        於現有 browser 內重建 context 並開啟 HAR 錄製
        Recreate the context with HAR recording enabled. Existing pages are
        closed; a fresh page is opened on the new context.
        """
        web_runner_logger.info(f"playwright start_har_recording: {har_path}")
        if self._browser is None:
            raise PlaywrightBackendError(_BROWSER_NOT_LAUNCHED)
        if self._context is not None:
            self._context.close()
        self._context = self._build_context(har_path, content)
        page = self._context.new_page()
        self._pages = [page]
        self._page_index = 0

    def stop_har_recording(self) -> None:
        """
        關閉並寫出當前 HAR，重建一個未錄製的 context
        Close the recording context (which flushes the HAR file) and replace
        it with a fresh non-recording context.
        """
        web_runner_logger.info("playwright stop_har_recording")
        if self._browser is None:
            raise PlaywrightBackendError(_BROWSER_NOT_LAUNCHED)
        if self._context is not None:
            self._context.close()
        self._context = self._browser.new_context()
        page = self._context.new_page()
        self._pages = [page]
        self._page_index = 0

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
            if self._playwright is not None:
                self._playwright.stop()
            self._playwright = None

    # ----- pages / tabs ------------------------------------------------

    def new_page(self) -> int:
        """Open a new page in the current context; returns its index."""
        page = self.context.new_page()
        self._pages.append(page)
        self._page_index = len(self._pages) - 1
        return self._page_index

    def switch_to_page(self, index: int) -> None:
        if index < 0 or index >= len(self._pages):
            raise PlaywrightBackendError(f"page index {index} out of range")
        self._page_index = index

    def close_page(self, index: Optional[int] = None) -> None:
        target_index = self._page_index if index is None else index
        if target_index < 0 or target_index >= len(self._pages):
            raise PlaywrightBackendError(f"page index {target_index} out of range")
        self._pages[target_index].close()
        del self._pages[target_index]
        if not self._pages:
            self._page_index = -1
        else:
            self._page_index = min(self._page_index, len(self._pages) - 1)

    def page_count(self) -> int:
        return len(self._pages)

    # ----- navigation --------------------------------------------------

    def to_url(self, url: str, **goto_options: Any) -> None:
        web_runner_logger.info(f"playwright to_url: {url}")
        params = {"url": url}
        try:
            self.page.goto(url, **goto_options)
            _record("to_url", params, None)
        except Exception as error:  # noqa: BLE001
            web_runner_logger.error(f"playwright to_url failed: {error!r}")
            _record("to_url", params, error)

    def forward(self) -> None:
        self.page.go_forward()

    def back(self) -> None:
        self.page.go_back()

    def refresh(self) -> None:
        self.page.reload()

    def url(self) -> str:
        return self.page.url

    def title(self) -> str:
        return self.page.title()

    def content(self) -> str:
        return self.page.content()

    def set_default_timeout(self, timeout_ms: float) -> None:
        self.page.set_default_timeout(timeout_ms)

    def set_default_navigation_timeout(self, timeout_ms: float) -> None:
        self.page.set_default_navigation_timeout(timeout_ms)

    # ----- finding -----------------------------------------------------

    def find_element(self, selector: str):
        web_runner_logger.info(f"playwright find_element: {selector}")
        return self.page.query_selector(selector)

    def find_elements(self, selector: str) -> List[Any]:
        web_runner_logger.info(f"playwright find_elements: {selector}")
        return self.page.query_selector_all(selector)

    def find_element_with_test_object_record(self, element_name: str):
        """
        Resolve ``element_name`` from ``test_object_record`` and capture the
        first matching element on ``element_wrapper``.
        """
        selector = selector_for_recorded_name(element_name)
        element = self.page.query_selector(selector)
        self.element_wrapper.current_element = element
        return element

    def find_elements_with_test_object_record(self, element_name: str):
        selector = selector_for_recorded_name(element_name)
        elements = self.page.query_selector_all(selector)
        self.element_wrapper.current_element_list = list(elements)
        if elements:
            self.element_wrapper.current_element = elements[0]
        return elements

    # ----- direct page-level element shortcuts ------------------------

    def click(self, selector: str, **options: Any) -> None:
        web_runner_logger.info(f"playwright click: {selector}")
        self.page.click(selector, **options)

    def dblclick(self, selector: str, **options: Any) -> None:
        self.page.dblclick(selector, **options)

    def hover(self, selector: str, **options: Any) -> None:
        self.page.hover(selector, **options)

    def fill(self, selector: str, value: str, **options: Any) -> None:
        web_runner_logger.info(f"playwright fill: {selector}")
        self.page.fill(selector, value, **options)

    def type_text(self, selector: str, value: str, delay: float = 0) -> None:
        self.page.type(selector, value, delay=delay)

    def press(self, selector: str, key: str) -> None:
        self.page.press(selector, key)

    def check(self, selector: str) -> None:
        self.page.check(selector)

    def uncheck(self, selector: str) -> None:
        self.page.uncheck(selector)

    def select_option(self, selector: str, value: Any) -> List[str]:
        return self.page.select_option(selector, value)

    def drag_and_drop(self, source_selector: str, target_selector: str, **options: Any) -> None:
        self.page.drag_and_drop(source_selector, target_selector, **options)

    # ----- script ------------------------------------------------------

    def evaluate(self, expression: str, arg: Any = None):
        return self.page.evaluate(expression, arg) if arg is not None else self.page.evaluate(expression)

    def evaluate_handle(self, expression: str, arg: Any = None):
        if arg is not None:
            return self.page.evaluate_handle(expression, arg)
        return self.page.evaluate_handle(expression)

    # ----- cookies -----------------------------------------------------

    def get_cookies(self) -> List[dict]:
        return self.context.cookies()

    def add_cookies(self, cookies: List[dict]) -> None:
        self.context.add_cookies(cookies)

    def clear_cookies(self) -> None:
        self.context.clear_cookies()

    # ----- screenshots -------------------------------------------------

    def screenshot(self, path: str, full_page: bool = False) -> str:
        self.page.screenshot(path=path, full_page=full_page)
        return path

    def screenshot_bytes(self, full_page: bool = False) -> bytes:
        return self.page.screenshot(full_page=full_page)

    # ----- waits -------------------------------------------------------

    def wait_for_selector(self, selector: str, timeout: Optional[float] = None, state: str = "visible"):
        if timeout is None:
            return self.page.wait_for_selector(selector, state=state)
        return self.page.wait_for_selector(selector, timeout=timeout, state=state)

    def wait_for_load_state(self, state: str = "load", timeout: Optional[float] = None) -> None:
        if timeout is None:
            self.page.wait_for_load_state(state)
        else:
            self.page.wait_for_load_state(state, timeout=timeout)

    def wait_for_timeout(self, timeout_ms: float) -> None:
        self.page.wait_for_timeout(timeout_ms)

    def wait_for_url(self, url: str, timeout: Optional[float] = None) -> None:
        if timeout is None:
            self.page.wait_for_url(url)
        else:
            self.page.wait_for_url(url, timeout=timeout)

    # ----- viewport / window ------------------------------------------

    def set_viewport_size(self, width: int, height: int) -> None:
        self.page.set_viewport_size({"width": width, "height": height})

    def viewport_size(self) -> Optional[dict]:
        return self.page.viewport_size

    # ----- mouse / keyboard -------------------------------------------

    def mouse_click(self, x: float, y: float, button: str = "left", click_count: int = 1) -> None:
        self.page.mouse.click(x, y, button=button, click_count=click_count)

    def mouse_move(self, x: float, y: float, steps: int = 1) -> None:
        self.page.mouse.move(x, y, steps=steps)

    def mouse_down(self, button: str = "left", click_count: int = 1) -> None:
        self.page.mouse.down(button=button, click_count=click_count)

    def mouse_up(self, button: str = "left", click_count: int = 1) -> None:
        self.page.mouse.up(button=button, click_count=click_count)

    def keyboard_press(self, key: str) -> None:
        self.page.keyboard.press(key)

    def keyboard_type(self, text: str, delay: float = 0) -> None:
        self.page.keyboard.type(text, delay=delay)

    def keyboard_down(self, key: str) -> None:
        self.page.keyboard.down(key)

    def keyboard_up(self, key: str) -> None:
        self.page.keyboard.up(key)

    # ----- frames ------------------------------------------------------

    def frames(self) -> List[Any]:
        return list(self.page.frames)

    def main_frame(self) -> Any:
        return self.page.main_frame

    # ----- network route mocking --------------------------------------

    def route_mock(self, url_pattern: str, response: dict) -> None:
        """
        將符合 ``url_pattern`` 的請求以 stub 回應
        Stub network requests matching ``url_pattern`` with a static response.

        ``response`` 支援 keys: ``status`` (int), ``body`` (str/bytes),
        ``headers`` (dict), ``content_type`` (str)。
        """
        web_runner_logger.info(f"playwright route_mock: {url_pattern}")
        fulfill_kwargs = {
            "status": response.get("status", 200),
            "body": response.get("body", ""),
            "headers": response.get("headers", {}),
        }
        if "content_type" in response:
            fulfill_kwargs["content_type"] = response["content_type"]

        def _handler(route, request):  # noqa: ARG001 — Playwright requires this signature
            route.fulfill(**fulfill_kwargs)

        self.page.route(url_pattern, _handler)

    def route_mock_json(self, url_pattern: str, json_data: Any, status: int = 200) -> None:
        """JSON 便捷版本 / Convenience for JSON responses."""
        import json as _json

        self.route_mock(
            url_pattern,
            {
                "status": status,
                "body": _json.dumps(json_data),
                "headers": {"Content-Type": "application/json"},
                "content_type": "application/json",
            },
        )

    def route_unmock(self, url_pattern: str) -> None:
        """Remove a specific route handler (Playwright will fall through to network)."""
        self.page.unroute(url_pattern)

    def route_clear(self) -> None:
        """Remove all route handlers on the current page."""
        self.page.unroute_all()


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


def pw_list_devices() -> List[str]:
    return playwright_wrapper_instance.list_device_names()


def pw_set_geolocation(latitude: float, longitude: float, accuracy: Optional[float] = None) -> None:
    playwright_wrapper_instance.set_geolocation(latitude, longitude, accuracy=accuracy)


def pw_grant_permissions(permissions: List[str], origin: Optional[str] = None) -> None:
    playwright_wrapper_instance.grant_permissions(permissions, origin=origin)


def pw_clear_permissions() -> None:
    playwright_wrapper_instance.clear_permissions()


def pw_set_timezone(timezone_id: str) -> None:
    playwright_wrapper_instance.set_timezone(timezone_id)


def pw_clock_install(fake_now_ms: Optional[float] = None) -> None:
    playwright_wrapper_instance.clock_install(fake_now_ms)


def pw_clock_set_time(time_ms: float) -> None:
    playwright_wrapper_instance.clock_set_time(time_ms)


def pw_clock_run_for(duration_ms: float) -> None:
    playwright_wrapper_instance.clock_run_for(duration_ms)


def pw_set_locale(locale: str, accept_language: Optional[str] = None) -> None:
    playwright_wrapper_instance.set_locale(locale, accept_language=accept_language)


def pw_quit() -> None:
    playwright_wrapper_instance.quit()


def pw_to_url(url: str) -> None:
    playwright_wrapper_instance.to_url(url)


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


def pw_close_page(index: Optional[int] = None) -> None:
    playwright_wrapper_instance.close_page(index)


def pw_page_count() -> int:
    return playwright_wrapper_instance.page_count()


def pw_find_element(selector: str):
    return playwright_wrapper_instance.find_element(selector)


def pw_find_elements(selector: str) -> List[Any]:
    return playwright_wrapper_instance.find_elements(selector)


def pw_find_element_with_test_object_record(element_name: str):
    return playwright_wrapper_instance.find_element_with_test_object_record(element_name)


def pw_find_elements_with_test_object_record(element_name: str):
    return playwright_wrapper_instance.find_elements_with_test_object_record(element_name)


def pw_click(selector: str) -> None:
    playwright_wrapper_instance.click(selector)


def pw_dblclick(selector: str) -> None:
    playwright_wrapper_instance.dblclick(selector)


def pw_hover(selector: str) -> None:
    playwright_wrapper_instance.hover(selector)


def pw_fill(selector: str, value: str) -> None:
    playwright_wrapper_instance.fill(selector, value)


def pw_type_text(selector: str, value: str, delay: float = 0) -> None:
    playwright_wrapper_instance.type_text(selector, value, delay=delay)


def pw_press(selector: str, key: str) -> None:
    playwright_wrapper_instance.press(selector, key)


def pw_check(selector: str) -> None:
    playwright_wrapper_instance.check(selector)


def pw_uncheck(selector: str) -> None:
    playwright_wrapper_instance.uncheck(selector)


def pw_select_option(selector: str, value: Any) -> List[str]:
    return playwright_wrapper_instance.select_option(selector, value)


def pw_drag_and_drop(source_selector: str, target_selector: str) -> None:
    playwright_wrapper_instance.drag_and_drop(source_selector, target_selector)


def pw_evaluate(expression: str, arg: Any = None):
    return playwright_wrapper_instance.evaluate(expression, arg)


def pw_get_cookies() -> List[dict]:
    return playwright_wrapper_instance.get_cookies()


def pw_add_cookies(cookies: List[dict]) -> None:
    playwright_wrapper_instance.add_cookies(cookies)


def pw_clear_cookies() -> None:
    playwright_wrapper_instance.clear_cookies()


def pw_screenshot(path: str, full_page: bool = False) -> str:
    return playwright_wrapper_instance.screenshot(path, full_page=full_page)


def pw_screenshot_bytes(full_page: bool = False) -> bytes:
    return playwright_wrapper_instance.screenshot_bytes(full_page=full_page)


def pw_wait_for_selector(selector: str, timeout: Optional[float] = None, state: str = "visible"):
    return playwright_wrapper_instance.wait_for_selector(selector, timeout=timeout, state=state)


def pw_wait_for_load_state(state: str = "load", timeout: Optional[float] = None) -> None:
    playwright_wrapper_instance.wait_for_load_state(state, timeout=timeout)


def pw_wait_for_timeout(timeout_ms: float) -> None:
    playwright_wrapper_instance.wait_for_timeout(timeout_ms)


def pw_wait_for_url(url: str, timeout: Optional[float] = None) -> None:
    playwright_wrapper_instance.wait_for_url(url, timeout=timeout)


def pw_set_viewport_size(width: int, height: int) -> None:
    playwright_wrapper_instance.set_viewport_size(width, height)


def pw_viewport_size() -> Optional[dict]:
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
