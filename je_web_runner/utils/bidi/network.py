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


def _add_request_handler(driver, event: str, callback: Callable[[Any], None]) -> int:
    """
    透過 Selenium 4.x BiDi ``network.add_request_handler(event, callback)``
    註冊一個事件 handler。legacy phase 入口以 ``event`` 區分階段
    (``before_request`` / ``auth_required``；``response_started`` 於
    Selenium 4.45 移除，改走原生 ``add_response_handler``)。
    Register a handler via Selenium 4.x BiDi ``add_request_handler(event, cb)``.
    """
    network = _resolve_network(driver)
    add = getattr(network, "add_request_handler", None)
    if add is None:
        raise BidiNetworkError(
            "driver.network.add_request_handler missing; needs Selenium 4.23+"
        )
    return add(event, callback)


def add_request_handler(driver, callback: Callable[[Any], None]) -> int:
    """
    註冊「請求送出前」事件 handler，回傳訂閱 id。
    Register a handler for the BiDi ``network.beforeRequestSent`` event.

    :param callback: 接收事件物件的可呼叫物 / callable taking an event object
    """
    web_runner_logger.info("bidi network add_request_handler")
    return _add_request_handler(driver, "before_request", callback)


def add_response_handler(driver, callback: Callable[[Any], None]) -> int | str:
    """
    註冊「回應開始」事件 handler，回傳訂閱 id。
    Register a handler for the BiDi ``network.responseStarted`` event.

    Selenium 4.45+ 提供原生 ``network.add_response_handler``（回傳字串
    handler id，callback 收到 ``Response`` 物件、Selenium 自動 continue）；
    更舊的版本退回 ``add_request_handler("response_started", ...)``
    （4.45 起該 legacy phase 已被移除，僅剩 before_request / auth_required）。
    Selenium 4.45+ exposes a native ``network.add_response_handler`` (string
    handler id; the callback receives a ``Response`` and Selenium continues it
    automatically); older versions fall back to the legacy
    ``add_request_handler("response_started", ...)`` phase, which 4.45 removed.
    """
    web_runner_logger.info("bidi network add_response_handler")
    network = _resolve_network(driver)
    native_add = getattr(network, "add_response_handler", None)
    if native_add is not None:
        return native_add(callback=callback)
    return _add_request_handler(driver, "response_started", callback)


def add_auth_handler(driver, callback: Callable[[Any], None]) -> int:
    """
    註冊 HTTP 401 / 407 認證挑戰 handler。
    Register a handler for the BiDi ``network.authRequired`` event. (Selenium's
    own ``add_auth_handler(username, password)`` auto-supplies credentials and
    is a different feature; this callback-based hook routes through
    ``add_request_handler('auth_required', ...)``.)
    """
    web_runner_logger.info("bidi network add_auth_handler")
    return _add_request_handler(driver, "auth_required", callback)


def clear_network_handlers(driver) -> bool:
    """
    一次清除所有透過本模組註冊的 network handlers。
    Clear every network handler previously registered through this module.
    """
    web_runner_logger.info("bidi network clear_network_handlers")
    network = _resolve_network(driver)
    clear = getattr(network, "clear_request_handlers", None)
    if clear is None:
        raise BidiNetworkError(
            "driver.network.clear_request_handlers missing; "
            "your Selenium version may not expose handler clearing"
        )
    # Selenium 4.45+ 的 clear_request_handlers 不會清到原生
    # add_response_handler 註冊的 handlers，要另外呼叫。
    # On Selenium 4.45+ clear_request_handlers does not cover handlers
    # registered via the native add_response_handler; clear those too.
    clear_responses = getattr(network, "clear_response_handlers", None)
    try:
        clear()
        if clear_responses is not None:
            clear_responses()
        return True
    except Exception as error:
        web_runner_logger.error(f"clear_network_handlers failed: {error!r}")
        return False
