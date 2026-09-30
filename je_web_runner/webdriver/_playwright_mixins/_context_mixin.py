"""Context 設定：裝置模擬、地理位置、權限、時區、時鐘、語系、HAR / Context-level settings."""
from __future__ import annotations

import re
from typing import Any

from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.webdriver._playwright_mixins._common import recorded
from je_web_runner.webdriver._playwright_mixins._common import (
    BROWSER_NOT_LAUNCHED,
    CLOCK_API_UNAVAILABLE,
    RUNTIME_NOT_STARTED,
    PlaywrightBackendError,
)

_HAR_KEYS = ("record_har_path", "record_har_content")


def _wildcard_regex(pattern: str) -> re.Pattern:
    """A whole-URL regex for a Selenium / CDP ``setBlockedURLs`` pattern, where ``*`` matches anything."""
    return re.compile("^" + ".*".join(re.escape(part) for part in pattern.split("*")) + "$")


def _abort(route: Any) -> None:
    route.abort()


def _fallback(route: Any) -> None:
    route.fallback()


class _ContextMixin:
    """裝置模擬、地理位置、權限、時區、時鐘、語系、HAR 錄製。

    Playwright fixes most of these when a context is created, so the wrapper keeps
    one merged set of context options (``_context_options``): each setting changes
    only its own keys and then rebuilds the context. A rebuild carries the cookies
    and localStorage over (``storage_state``) and reopens the page's URL, so a test
    can change the timezone mid-flow without losing its session. Geolocation,
    permissions, extra headers and the clock apply to the live context instead.
    """

    # ----- the merged options ------------------------------------------

    def _rebuild_context(self) -> None:
        """Close the context and open one with the current options, keeping cookies, storage and the URL."""
        if self._fixed_context:
            raise PlaywrightBackendError(
                "this context was attached (connect_over_cdp) or is persistent, so its options are fixed; "
                "pass them to launch_persistent, or launch a new browser"
            )
        if self._browser is None:
            raise PlaywrightBackendError(BROWSER_NOT_LAUNCHED)
        state, url = None, None
        if self._context is not None:
            state, url = self._context.storage_state(), self._current_page_url()
            self._context.close()
        self._context = self._open_context(storage_state=state)
        page = self._context.new_page()
        self._reset_pages(page)
        if isinstance(url, str) and url.startswith(("http://", "https://")):
            try:
                page.goto(url)
            except Exception as error:  # the new context stands; the reload is a convenience
                web_runner_logger.warning(f"playwright could not reopen {url!r} after a context rebuild: {error!r}")

    def _current_page_url(self) -> Any:
        if not self._pages or self._page_index < 0:
            return None
        return self._pages[self._page_index].url

    @recorded()
    def set_context_options(self, **options: Any) -> None:
        """
        合併任意 ``browser.new_context`` 選項並重建 context
        Merge any ``browser.new_context`` options (``color_scheme``, ``viewport``,
        ``ignore_https_errors``, ``storage_state`` …) and rebuild the context.
        """
        web_runner_logger.info(f"playwright set_context_options: {sorted(options)}")
        self._context_options.update(options)
        self._rebuild_context()

    @recorded()
    def set_user_agent(self, user_agent: str) -> None:
        """Rebuild the context with ``user_agent``."""
        self._context_options["user_agent"] = user_agent
        self._rebuild_context()

    @recorded(hidden=("headers",))
    def set_extra_http_headers(self, headers: dict[str, str]) -> None:
        """
        合併額外的 HTTP header，立即套用於目前的 context
        Merge ``headers`` into the extra HTTP headers sent with every request; they
        apply to the live context at once and to every rebuilt one.
        """
        merged = {**(self._context_options.get("extra_http_headers") or {}), **headers}
        self._context_options["extra_http_headers"] = merged
        self.context.set_extra_http_headers(merged)

    def _reapply_context_setup(self, context: Any) -> None:
        """Give a freshly opened context the init scripts and URL blocks set so far."""
        for source in self._init_scripts:
            context.add_init_script(source)
        for pattern in self._blocked_urls:
            context.route(pattern, _abort)
        if self._cache_route is not None:
            context.route("**/*", self._cache_route)

    @recorded()
    def add_init_script(self, source: str) -> None:
        """
        在每份新文件的腳本執行前注入 JavaScript
        Run ``source`` in every new document before its own scripts, in every page of
        this context and of rebuilt ones. Behind the arbitrary-script gate.
        """
        self._init_scripts.append(source)
        self.context.add_init_script(source)

    @recorded()
    def block_urls(self, patterns: list[str]) -> None:
        """
        阻擋符合任一 pattern 的請求（``*`` 萬用字元，比對整個 URL）
        Abort requests whose whole URL matches any pattern; ``*`` matches anything,
        as in Selenium's ``WR_block_urls`` (e.g. ``"*.doubleclick.net/*"``).
        """
        for pattern in patterns:
            regex = _wildcard_regex(pattern)
            self._blocked_urls.append(regex)
            self.context.route(regex, _abort)

    @recorded()
    def unblock_urls(self) -> None:
        """Remove every block added by :meth:`block_urls`."""
        for regex in self._blocked_urls:
            self.context.unroute(regex)
        self._blocked_urls = []

    @recorded()
    def set_cache_disabled(self, disabled: bool = True) -> None:
        """
        停用（或恢復）HTTP 快取
        Disable the HTTP cache (``True``) or restore it (``False``). Playwright turns the
        cache off whenever a route is active, so this adds a route that passes every
        request on (``fallback``, leaving URL blocks and mocks in effect); works on every
        browser, unlike Selenium's CDP ``WR_set_cache_disabled``.
        """
        if disabled and self._cache_route is None:
            self._cache_route = _fallback
            self.context.route("**/*", _fallback)
        elif not disabled and self._cache_route is not None:
            self.context.unroute("**/*", self._cache_route)
            self._cache_route = None

    @recorded()
    def clear_geolocation(self) -> None:
        """Remove the geolocation override."""
        self.context.set_geolocation(None)

    def save_storage_state(self, path: str) -> str:
        """Write the context's cookies and localStorage to ``path`` (load it with ``storage_state``)."""
        self.context.storage_state(path=path)
        return path

    # ----- emulation ---------------------------------------------------

    def _device_options(self, device_name: str) -> dict:
        """Look up Playwright's built-in device descriptor by name."""
        if self._playwright is None:
            raise PlaywrightBackendError(RUNTIME_NOT_STARTED)
        devices = getattr(self._playwright, "devices", None)
        if not devices or device_name not in devices:
            available = sorted(devices.keys()) if devices else []
            raise PlaywrightBackendError(
                f"unknown device {device_name!r}; available examples: {available[:5]}"
            )
        return dict(devices[device_name])

    @recorded()
    def start_emulation(self, device_name: str) -> None:
        """
        套用 Playwright 內建裝置設定（重建 context）
        Apply a Playwright device descriptor by name on top of the other options.
        """
        web_runner_logger.info(f"playwright start_emulation: {device_name}")
        device = self._device_options(device_name)
        for key in self._emulation_keys:
            self._context_options.pop(key, None)
        self._context_options.update(device)
        self._emulation_keys = set(device)
        self._rebuild_context()

    @recorded()
    def stop_emulation(self) -> None:
        """Drop the device descriptor's options (the other options stay) and rebuild."""
        web_runner_logger.info("playwright stop_emulation")
        for key in self._emulation_keys:
            self._context_options.pop(key, None)
        self._emulation_keys = set()
        self._rebuild_context()

    def list_device_names(self) -> list[str]:
        """Return all device names known to the active Playwright runtime."""
        if self._playwright is None:
            raise PlaywrightBackendError(RUNTIME_NOT_STARTED)
        devices = getattr(self._playwright, "devices", None) or {}
        return sorted(devices.keys())

    # ----- geolocation / permissions / timezone / locale / clock --------

    @recorded()
    def set_geolocation(
        self,
        latitude: float,
        longitude: float,
        accuracy: float | None = None,
    ) -> None:
        """Set the page geolocation; remember to grant ``geolocation`` permission first."""
        web_runner_logger.info(f"playwright set_geolocation: {latitude}, {longitude}")
        coords: dict[str, float] = {"latitude": latitude, "longitude": longitude}
        if accuracy is not None:
            coords["accuracy"] = accuracy
        self.context.set_geolocation(coords)

    @recorded()
    def grant_permissions(
        self,
        permissions: list[str],
        origin: str | None = None,
    ) -> None:
        """Grant browser permissions (e.g. ``geolocation`` / ``clipboard-read``)."""
        if origin is None:
            self.context.grant_permissions(permissions)
        else:
            self.context.grant_permissions(permissions, origin=origin)

    @recorded()
    def clear_permissions(self) -> None:
        self.context.clear_permissions()

    @recorded()
    def set_timezone(self, timezone_id: str) -> None:
        """
        指定時區並重建 context（Playwright 不能修改既有 context 的時區）
        Rebuild the context with ``timezone_id``.
        """
        web_runner_logger.info(f"playwright set_timezone: {timezone_id}")
        self._context_options["timezone_id"] = timezone_id
        self._rebuild_context()

    @recorded()
    def set_locale(
        self,
        locale: str,
        accept_language: str | None = None,
    ) -> None:
        """
        切換 ``locale`` 與 ``Accept-Language``（重建 context）
        Rebuild the context with ``locale``; ``accept_language`` is merged into the
        extra HTTP headers.
        """
        web_runner_logger.info(f"playwright set_locale: {locale}")
        self._context_options["locale"] = locale
        if accept_language:
            headers = dict(self._context_options.get("extra_http_headers") or {})
            headers["Accept-Language"] = accept_language
            self._context_options["extra_http_headers"] = headers
        self._rebuild_context()

    def _clock(self) -> Any:
        clock = getattr(self.context, "clock", None)
        if clock is None:
            raise PlaywrightBackendError(CLOCK_API_UNAVAILABLE)
        return clock

    @recorded()
    def clock_install(self, fake_now_ms: float | None = None) -> None:
        """Install Playwright's clock (requires Playwright 1.45+)."""
        if fake_now_ms is None:
            self._clock().install()
        else:
            self._clock().install(time=fake_now_ms)

    @recorded()
    def clock_set_time(self, time_ms: float) -> None:
        self._clock().set_fixed_time(time_ms)

    @recorded()
    def clock_run_for(self, duration_ms: float) -> None:
        self._clock().run_for(duration_ms)

    # ----- HAR ---------------------------------------------------------

    @recorded()
    def start_har_recording(self, har_path: str, content: str = "omit") -> None:
        """
        開啟 HAR 錄製（重建 context）
        Rebuild the context with HAR recording to ``har_path``; the other options stay.
        """
        web_runner_logger.info(f"playwright start_har_recording: {har_path}")
        self._context_options.update({"record_har_path": har_path, "record_har_content": content})
        self._rebuild_context()

    @recorded()
    def stop_har_recording(self) -> None:
        """
        寫出 HAR 並停止錄製
        Close the recording context, which writes the HAR file, and continue in one
        without recording.
        """
        web_runner_logger.info("playwright stop_har_recording")
        for key in _HAR_KEYS:
            self._context_options.pop(key, None)
        self._rebuild_context()
