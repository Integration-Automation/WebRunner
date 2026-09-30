"""Context 設定：裝置模擬、地理位置、權限、時區、時鐘、語系、HAR / Context-level settings."""
from __future__ import annotations

from typing import Any

from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.webdriver._playwright_mixins._common import recorded
from je_web_runner.webdriver._playwright_mixins._common import (
    BROWSER_NOT_LAUNCHED,
    CLOCK_API_UNAVAILABLE,
    RUNTIME_NOT_STARTED,
    PlaywrightBackendError,
)


class _ContextMixin:
    """裝置模擬、地理位置、權限、時區、時鐘、語系、HAR 錄製。

    Device emulation, geolocation, permissions, timezone, clock, locale and HAR
    recording. Several of these rebuild the context (Playwright fixes them at
    context creation).
    """

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
        套用 Playwright 內建裝置設定（重建 context 與 page）
        Apply a Playwright device descriptor by name; the current context is
        closed and replaced with one configured for the requested device.
        """
        web_runner_logger.info(f"playwright start_emulation: {device_name}")
        if self._browser is None:
            raise PlaywrightBackendError(BROWSER_NOT_LAUNCHED)
        if self._context is not None:
            self._context.close()
        self._context = self._build_context(extra_options=self._device_options(device_name))
        page = self._context.new_page()
        self._pages = [page]
        self._page_index = 0

    @recorded()
    def stop_emulation(self) -> None:
        """Replace the device-emulating context with a plain one."""
        web_runner_logger.info("playwright stop_emulation")
        if self._browser is None:
            raise PlaywrightBackendError(BROWSER_NOT_LAUNCHED)
        if self._context is not None:
            self._context.close()
        self._context = self._build_context()
        page = self._context.new_page()
        self._pages = [page]
        self._page_index = 0

    # ----- geolocation / permissions / timezone / clock --------------

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
        重建 context 並指定時區（Playwright 不支援直接修改既有 context 的時區）
        Recreate the context with ``timezoneId``; the existing page is closed.
        """
        web_runner_logger.info(f"playwright set_timezone: {timezone_id}")
        if self._browser is None:
            raise PlaywrightBackendError(BROWSER_NOT_LAUNCHED)
        if self._context is not None:
            self._context.close()
        self._context = self._build_context(extra_options={"timezone_id": timezone_id})
        page = self._context.new_page()
        self._pages = [page]
        self._page_index = 0

    @recorded()
    def clock_install(self, fake_now_ms: float | None = None) -> None:
        """Install Playwright's clock (requires Playwright 1.45+)."""
        clock = getattr(self.context, "clock", None)
        if clock is None:
            raise PlaywrightBackendError(CLOCK_API_UNAVAILABLE)
        if fake_now_ms is None:
            clock.install()
        else:
            clock.install(time=fake_now_ms)

    @recorded()
    def clock_set_time(self, time_ms: float) -> None:
        clock = getattr(self.context, "clock", None)
        if clock is None:
            raise PlaywrightBackendError(CLOCK_API_UNAVAILABLE)
        clock.set_fixed_time(time_ms)

    @recorded()
    def clock_run_for(self, duration_ms: float) -> None:
        clock = getattr(self.context, "clock", None)
        if clock is None:
            raise PlaywrightBackendError(CLOCK_API_UNAVAILABLE)
        clock.run_for(duration_ms)

    @recorded()
    def set_locale(
        self,
        locale: str,
        accept_language: str | None = None,
    ) -> None:
        """
        切換 ``locale`` 與 ``Accept-Language``（重建 context）
        Recreate the context with the given ``locale`` (and optional
        Accept-Language override). The current page is closed.
        """
        web_runner_logger.info(f"playwright set_locale: {locale}")
        if self._browser is None:
            raise PlaywrightBackendError(BROWSER_NOT_LAUNCHED)
        options: dict[str, Any] = {"locale": locale}
        if accept_language:
            options["extra_http_headers"] = {"Accept-Language": accept_language}
        if self._context is not None:
            self._context.close()
        self._context = self._build_context(extra_options=options)
        page = self._context.new_page()
        self._pages = [page]
        self._page_index = 0

    def list_device_names(self) -> list[str]:
        """Return all device names known to the active Playwright runtime."""
        if self._playwright is None:
            raise PlaywrightBackendError(RUNTIME_NOT_STARTED)
        devices = getattr(self._playwright, "devices", None) or {}
        return sorted(devices.keys())

    @recorded()
    def start_har_recording(self, har_path: str, content: str = "omit") -> None:
        """
        於現有 browser 內重建 context 並開啟 HAR 錄製
        Recreate the context with HAR recording enabled. Existing pages are
        closed; a fresh page is opened on the new context.
        """
        web_runner_logger.info(f"playwright start_har_recording: {har_path}")
        if self._browser is None:
            raise PlaywrightBackendError(BROWSER_NOT_LAUNCHED)
        if self._context is not None:
            self._context.close()
        self._context = self._build_context(har_path, content)
        page = self._context.new_page()
        self._pages = [page]
        self._page_index = 0

    @recorded()
    def stop_har_recording(self) -> None:
        """
        關閉並寫出當前 HAR，重建一個未錄製的 context
        Close the recording context (which flushes the HAR file) and replace
        it with a fresh non-recording context.
        """
        web_runner_logger.info("playwright stop_har_recording")
        if self._browser is None:
            raise PlaywrightBackendError(BROWSER_NOT_LAUNCHED)
        if self._context is not None:
            self._context.close()
        self._context = self._build_context()
        page = self._context.new_page()
        self._pages = [page]
        self._page_index = 0
