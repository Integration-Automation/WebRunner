"""Cookie、截圖、等待、viewport、網路 route / Cookies, screenshots, waits, viewport, routes."""
from __future__ import annotations

from typing import Any

from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class _StateMixin:
    """Cookie、截圖、等待條件、viewport 與網路 route 模擬。

    Cookies, screenshots, wait conditions, viewport size and network route
    mocking.
    """

    def get_cookies(self) -> list[dict]:
        return self.context.cookies()

    def add_cookies(self, cookies: list[dict]) -> None:
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

    def wait_for_selector(self, selector: str, timeout: float | None = None, state: str = "visible"):
        if timeout is None:
            return self.page.wait_for_selector(selector, state=state)
        return self.page.wait_for_selector(selector, timeout=timeout, state=state)

    def wait_for_load_state(self, state: str = "load", timeout: float | None = None) -> None:
        if timeout is None:
            self.page.wait_for_load_state(state)
        else:
            self.page.wait_for_load_state(state, timeout=timeout)

    def wait_for_timeout(self, timeout_ms: float) -> None:
        self.page.wait_for_timeout(timeout_ms)

    def wait_for_url(self, url: str, timeout: float | None = None) -> None:
        if timeout is None:
            self.page.wait_for_url(url)
        else:
            self.page.wait_for_url(url, timeout=timeout)

    # ----- viewport / window ------------------------------------------

    def set_viewport_size(self, width: int, height: int) -> None:
        self.page.set_viewport_size({"width": width, "height": height})

    def viewport_size(self) -> dict | None:
        return self.page.viewport_size

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

        def _handler(route, request):
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
