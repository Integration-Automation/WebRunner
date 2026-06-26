"""
CDP 事件迴圈：背景執行緒從 Chrome DevTools Protocol WebSocket 接收事件，
並以同步 callback 派發給使用者。
Background CDP event loop: reads events from the Chrome DevTools Protocol
WebSocket on a worker thread and dispatches them to user callbacks
synchronously.

為什麼存在 / Why this module exists
----------------------------------
``webdriver_wrapper_instance.execute_cdp_cmd`` 走 Selenium 內部 session，
是一次性命令，不會把後續 CDP 事件 (例如 ``Fetch.requestPaused`` /
``Tracing.dataCollected``) 推給使用者。要訂閱事件，唯一可靠的同步路徑是
**獨立開一條 CDP WebSocket** — 本模組就是做這件事。

``execute_cdp_cmd`` issues one-shot CDP commands through Selenium's internal
session but never surfaces subsequent CDP events (e.g.
``Fetch.requestPaused`` / ``Tracing.dataCollected``) back to user code.
The only reliable synchronous path to subscribe to events is to open a
**separate CDP WebSocket connection** — that's what this module does.

限制 / Limitations
-----------------
* 需要 ``websocket-client`` 套件 (``pip install websocket-client``)。
  Requires the ``websocket-client`` package.
* 僅 Chromium 系瀏覽器 (Chrome / Chromium / Edge)。
  Chromium-family browsers only.
* 為了讓事件與命令在同一個 CDP target session 上，命令請改用
  ``listener.send(method, params)`` 而不是 ``execute_cdp_cmd`` — 不同 session
  發出的命令不會把事件路由到本 listener。
  Use ``listener.send(method, params)`` to issue commands so they share the
  same target session as event subscriptions; ``execute_cdp_cmd`` lives on a
  different Selenium-managed session and its events won't reach this listener.
"""
from __future__ import annotations

import json
import queue
import threading
from typing import Any, Callable, Dict, List, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class CDPEventLoopError(WebRunnerException):
    """Raised when the CDP event loop cannot operate."""


def _require_websocket_client():
    """惰性匯入 websocket-client；缺少時拋出友善錯誤。"""
    try:
        import websocket  # type: ignore[import-not-found]
    except ImportError as error:
        raise CDPEventLoopError(
            "websocket-client is required for CDPEventListener; "
            "install with: pip install websocket-client"
        ) from error
    return websocket


def _query_page_ws_url(debugger_address: str) -> str:
    """從 ``http://host:port/json`` 取出第一個 page target 的 WebSocket URL。"""
    import urllib.request

    # Chrome / Edge DevTools 的 ``/json`` discovery endpoint 只跑在
    # ``--remote-debugging-port`` 上，協議固定為 HTTP 且只 bind localhost。
    # 不支援 HTTPS — 換 https 會直接連線失敗。
    # The Chrome / Edge DevTools ``/json`` discovery endpoint runs only on
    # the ``--remote-debugging-port``, is HTTP-only by browser design, and
    # binds to localhost. Forcing https here would simply fail to connect.
    url = f"http://{debugger_address}/json"  # NOSONAR python:S5332 — DevTools endpoint is HTTP-only by design
    # Bandit B310: scheme is fixed-literal ``http://`` above, not user-controlled — only
    # ``debugger_address`` (host:port) varies, so no file:// or custom-scheme risk.
    with urllib.request.urlopen(url, timeout=5) as response:  # nosec B310
        targets = json.loads(response.read())
    pages = [t for t in targets if t.get("type") == "page"]
    if not pages:
        raise CDPEventLoopError(f"no page targets at {debugger_address}")
    ws_url = pages[0].get("webSocketDebuggerUrl")
    if not ws_url:
        raise CDPEventLoopError(f"no webSocketDebuggerUrl in {pages[0]!r}")
    return ws_url


def resolve_cdp_ws_url(driver) -> str:
    """
    從 Selenium driver 解析出可用的 CDP WebSocket URL。
    Resolve a usable CDP WebSocket URL from a Selenium driver.

    優先順序 / Order of preference:
      1. ``driver.capabilities['goog:chromeOptions'].debuggerAddress`` 對應的 page WS
      2. ``driver.capabilities['ms:edgeOptions'].debuggerAddress``
      3. ``driver.capabilities['se:cdp']`` (Selenium 內建，通常為 browser-level)
    """
    capabilities = getattr(driver, "capabilities", None) or {}
    chrome_opts = capabilities.get("goog:chromeOptions") or {}
    edge_opts = capabilities.get("ms:edgeOptions") or {}
    debugger_address = (
        chrome_opts.get("debuggerAddress") or edge_opts.get("debuggerAddress")
    )
    if debugger_address:
        return _query_page_ws_url(debugger_address)
    se_cdp = capabilities.get("se:cdp")
    if se_cdp:
        return se_cdp
    raise CDPEventLoopError(
        "cannot resolve CDP WebSocket URL from driver capabilities"
    )


class CDPEventListener:
    """
    背景 CDP 事件迴圈，搭配同一條 WebSocket 同時送命令 / 收事件。
    Background CDP event loop sharing one WebSocket for sending commands
    and receiving events.

    典型用法 / Typical usage::

        with CDPEventListener.from_driver(driver) as listener:
            listener.on("Fetch.requestPaused", on_paused)
            listener.send("Fetch.enable", {"patterns": [{"urlPattern": "*"}]})
            # ... do work ...
    """

    def __init__(self, ws_url: str):
        self._ws_url = ws_url
        self._ws = None
        self._thread: Optional[threading.Thread] = None
        self._stop_flag = threading.Event()
        self._handlers: Dict[str, List[Callable[[dict], None]]] = {}
        self._handlers_lock = threading.Lock()
        self._pending: Dict[int, queue.Queue] = {}
        self._pending_lock = threading.Lock()
        self._next_id_lock = threading.Lock()
        self._next_id = 1

    @classmethod
    def from_driver(cls, driver) -> "CDPEventListener":
        """從現有 driver 自動解析 WebSocket URL 並建立 listener。"""
        return cls(resolve_cdp_ws_url(driver))

    def __enter__(self) -> "CDPEventListener":
        self.start()
        return self

    def __exit__(self, *_args) -> None:
        self.stop()

    def on(self, method: str, callback: Callable[[dict], None]) -> None:
        """訂閱指定 CDP 事件 / Subscribe to a CDP event."""
        with self._handlers_lock:
            self._handlers.setdefault(method, []).append(callback)

    def off(self, method: str, callback: Callable[[dict], None]) -> bool:
        """取消單一訂閱 (回傳是否成功移除)。"""
        with self._handlers_lock:
            handlers = self._handlers.get(method)
            if not handlers:
                return False
            try:
                handlers.remove(callback)
                return True
            except ValueError:
                return False

    def start(self) -> None:
        """開啟 WebSocket 並啟動背景接收執行緒 (重複呼叫安全)。"""
        if self._thread is not None and self._thread.is_alive():
            return
        websocket = _require_websocket_client()
        try:
            self._ws = websocket.create_connection(self._ws_url, timeout=10)
        except Exception as error:
            raise CDPEventLoopError(
                f"failed to open CDP WebSocket at {self._ws_url}: {error!r}"
            ) from error
        self._stop_flag.clear()
        self._thread = threading.Thread(
            target=self._run, name="CDPEventListener", daemon=True
        )
        self._thread.start()

    def stop(self, join_timeout: float = 2.0) -> None:
        """停止背景執行緒並關閉 WebSocket。"""
        self._stop_flag.set()
        ws = self._ws
        self._ws = None
        if ws is not None:
            try:
                ws.close()
            except Exception as error:
                web_runner_logger.debug(f"CDPEventListener ws.close failed: {error!r}")
        thread = self._thread
        self._thread = None
        if thread is not None and thread.is_alive():
            thread.join(timeout=join_timeout)

    def send(
            self,
            method: str,
            params: Optional[dict] = None,
            timeout: float = 5.0,
    ) -> Any:
        """
        發送 CDP 命令並等待回應 (與事件共用同一個 session)。
        Send a CDP command and block for the response (same session as events).
        """
        if self._ws is None:
            raise CDPEventLoopError("listener not started; call start() first")
        msg_id = self._allocate_id()
        reply_queue: queue.Queue = queue.Queue(maxsize=1)
        with self._pending_lock:
            self._pending[msg_id] = reply_queue
        payload = json.dumps({"id": msg_id, "method": method, "params": params or {}})
        try:
            self._ws.send(payload)
        except Exception as error:
            with self._pending_lock:
                self._pending.pop(msg_id, None)
            raise CDPEventLoopError(f"failed to send {method!r}: {error!r}") from error
        try:
            reply = reply_queue.get(timeout=timeout)
        except queue.Empty as error:
            with self._pending_lock:
                self._pending.pop(msg_id, None)
            raise CDPEventLoopError(
                f"timeout ({timeout}s) waiting for reply to {method!r}"
            ) from error
        if "error" in reply:
            raise CDPEventLoopError(f"CDP error for {method!r}: {reply['error']!r}")
        return reply.get("result", {})

    def _allocate_id(self) -> int:
        with self._next_id_lock:
            value = self._next_id
            self._next_id += 1
            return value

    def _run(self) -> None:
        """背景執行緒主迴圈：讀 WS → 解析 → 派發。"""
        while not self._stop_flag.is_set():
            ws = self._ws
            if ws is None:
                break
            try:
                raw = ws.recv()
            except Exception as error:
                if not self._stop_flag.is_set():
                    web_runner_logger.error(f"CDPEventListener recv failed: {error!r}")
                break
            if not raw:
                continue
            try:
                message = json.loads(raw)
            except Exception as error:
                web_runner_logger.warning(f"CDPEventListener bad JSON: {error!r}")
                continue
            self._dispatch(message)

    def _dispatch(self, message: dict) -> None:
        msg_id = message.get("id")
        if msg_id is not None:
            with self._pending_lock:
                reply_queue = self._pending.pop(msg_id, None)
            if reply_queue is not None:
                reply_queue.put(message)
            return
        method = message.get("method")
        if not method:
            return
        with self._handlers_lock:
            handlers = list(self._handlers.get(method, []))
        params = message.get("params") or {}
        for callback in handlers:
            try:
                callback(params)
            except Exception as error:
                web_runner_logger.error(
                    f"CDPEventListener handler for {method!r} raised: {error!r}"
                )
