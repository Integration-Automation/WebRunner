"""
W3C WebDriver BiDi Network 模組薄包裝 (Selenium 4.16+)。
Thin wrappers around the W3C WebDriver BiDi Network surface (Selenium 4.16+).

優於 CDP Fetch 之處 / Why prefer this over CDP Fetch
--------------------------------------------------
* **跨瀏覽器** — BiDi 是 W3C 標準，Chromium 與 Firefox 都支援；CDP Fetch 僅
  Chromium 系。
  **Cross-browser** — BiDi is a W3C standard supported by Chromium and Firefox;
  CDP Fetch is Chromium-only.
* **同步 callback 由 Selenium 內部派發** — 不必自行建 WebSocket 事件迴圈。
  **Sync callbacks dispatched by Selenium** — no need to build your own
  WebSocket event loop.

需求 / Requirements
------------------
* Selenium 4.16+ (BiDi Network surface 從這版開始穩定)
* driver 啟動時需開 BiDi：``set_driver(..., enable_bidi=True)``
* Firefox 也支援，但需要 ``geckodriver`` 0.34+
"""
from __future__ import annotations

from typing import Any, Callable

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class BidiNetworkError(WebRunnerException):
    """Raised when BiDi network API is unavailable or fails."""


def _resolve_network(driver) -> Any:
    """取得並驗證 ``driver.network`` 服務可用 / Resolve and validate driver.network."""
    network = getattr(driver, "network", None)
    if network is None:
        raise BidiNetworkError(
            "BiDi network unavailable: driver has no 'network' attribute. "
            "Use set_driver(enable_bidi=True) and Selenium >= 4.16."
        )
    return network


def add_request_handler(driver, callback: Callable[[Any], None]) -> int:
    """
    註冊「請求送出前」事件 handler，回傳訂閱 id。
    Register a handler for the BiDi ``network.beforeRequestSent`` event;
    returns a subscription id.

    :param callback: 接收事件物件的可呼叫物 / callable taking an event object
    """
    web_runner_logger.info("bidi network add_request_handler")
    try:
        return _resolve_network(driver).add_request_handler(callback)
    except AttributeError as error:
        raise BidiNetworkError(
            "driver.network.add_request_handler missing; needs Selenium 4.23+"
        ) from error


def add_response_handler(driver, callback: Callable[[Any], None]) -> int:
    """
    註冊「收到回應」事件 handler，回傳訂閱 id。
    Register a handler for the BiDi ``network.responseCompleted`` event;
    returns a subscription id.
    """
    web_runner_logger.info("bidi network add_response_handler")
    try:
        return _resolve_network(driver).add_response_handler(callback)
    except AttributeError as error:
        raise BidiNetworkError(
            "driver.network.add_response_handler missing; needs Selenium 4.23+"
        ) from error


def add_auth_handler(driver, callback: Callable[[Any], None]) -> int:
    """
    註冊 HTTP 401 / 407 認證挑戰 handler。
    Register a handler for the BiDi ``network.authRequired`` event.
    """
    web_runner_logger.info("bidi network add_auth_handler")
    try:
        return _resolve_network(driver).add_auth_handler(callback)
    except AttributeError as error:
        raise BidiNetworkError(
            "driver.network.add_auth_handler missing; needs Selenium 4.23+"
        ) from error


def clear_network_handlers(driver) -> bool:
    """
    一次清除所有透過本模組註冊的 network handlers。
    Clear every network handler previously registered through this module.
    """
    web_runner_logger.info("bidi network clear_network_handlers")
    network = _resolve_network(driver)
    clear = getattr(network, "clear_handlers", None) or getattr(network, "clear", None)
    if clear is None:
        raise BidiNetworkError(
            "driver.network has neither clear_handlers nor clear; "
            "your Selenium version may not expose handler clearing"
        )
    try:
        clear()
        return True
    except Exception as error:  # noqa: BLE001 — surface a friendlier wrapper
        web_runner_logger.error(f"clear_network_handlers failed: {error!r}")
        return False
