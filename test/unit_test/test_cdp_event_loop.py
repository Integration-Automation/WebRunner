"""
CDPEventListener / resolve_cdp_ws_url 的 mock-based 測試。
Mock-based tests for CDPEventListener and resolve_cdp_ws_url.

不需要真的瀏覽器；我們替換 ``_require_websocket_client`` 來注入 FakeWebSocket。
No real browser required; ``_require_websocket_client`` is patched to inject
a FakeWebSocket.
"""
from __future__ import annotations

import json
import threading
import time
import unittest
from collections import deque
from unittest.mock import MagicMock, patch

from je_web_runner.utils.cdp.event_loop import (
    CDPEventListener,
    CDPEventLoopError,
    resolve_cdp_ws_url,
)


class FakeWebSocket:
    """同步、執行緒安全的 fake WebSocket，給 listener 用。"""

    def __init__(self):
        self._inbox: deque = deque()
        self._lock = threading.Lock()
        self._not_empty = threading.Condition(self._lock)
        self.sent: list = []
        self.closed = False

    def push_message(self, message: str) -> None:
        with self._not_empty:
            self._inbox.append(message)
            self._not_empty.notify()

    def push_dict(self, data: dict) -> None:
        self.push_message(json.dumps(data))

    def send(self, data: str) -> None:
        if self.closed:
            raise OSError("closed")
        self.sent.append(data)

    def recv(self) -> str:
        with self._not_empty:
            while not self._inbox and not self.closed:
                self._not_empty.wait(timeout=0.05)
            if self._inbox:
                return self._inbox.popleft()
            raise OSError("closed")

    def close(self) -> None:
        with self._not_empty:
            self.closed = True
            self._not_empty.notify_all()


def _patch_websocket(fake_ws: FakeWebSocket):
    """回傳一個 patch context manager，將 _require_websocket_client 改為 fake。"""
    fake_module = MagicMock()
    fake_module.create_connection.return_value = fake_ws
    return patch(
        "je_web_runner.utils.cdp.event_loop._require_websocket_client",
        return_value=fake_module,
    )


def _wait_until(predicate, timeout=1.0, step=0.01) -> bool:
    """忙等 predicate 為真，timeout 後回 False。"""
    end = time.time() + timeout
    while time.time() < end:
        if predicate():
            return True
        time.sleep(step)
    return predicate()


class TestCDPEventListenerLifecycle(unittest.TestCase):

    def test_context_manager_starts_and_stops(self):
        fake_ws = FakeWebSocket()
        with _patch_websocket(fake_ws):
            with CDPEventListener("ws://fake") as listener:
                self.assertIsNotNone(listener._thread)
                self.assertTrue(listener._thread.is_alive())
        # 退出 context 後 thread 應收尾
        self.assertTrue(fake_ws.closed)

    def test_start_is_idempotent(self):
        fake_ws = FakeWebSocket()
        with _patch_websocket(fake_ws):
            listener = CDPEventListener("ws://fake")
            listener.start()
            first_thread = listener._thread
            listener.start()
            self.assertIs(listener._thread, first_thread)
            listener.stop()

    def test_missing_websocket_client_raises(self):
        def fake_require():
            raise CDPEventLoopError("websocket-client is required ...")

        with patch(
            "je_web_runner.utils.cdp.event_loop._require_websocket_client",
            side_effect=fake_require,
        ):
            listener = CDPEventListener("ws://fake")
            with self.assertRaises(CDPEventLoopError):
                listener.start()

    def test_create_connection_failure_wrapped(self):
        fake_module = MagicMock()
        fake_module.create_connection.side_effect = OSError("refused")
        with patch(
            "je_web_runner.utils.cdp.event_loop._require_websocket_client",
            return_value=fake_module,
        ):
            listener = CDPEventListener("ws://fake")
            with self.assertRaises(CDPEventLoopError):
                listener.start()


class TestCDPEventListenerDispatch(unittest.TestCase):

    def test_event_dispatched_to_handler(self):
        fake_ws = FakeWebSocket()
        received = []
        with _patch_websocket(fake_ws):
            with CDPEventListener("ws://fake") as listener:
                listener.on(
                    "Fetch.requestPaused",
                    lambda params: received.append(params),
                )
                fake_ws.push_dict({
                    "method": "Fetch.requestPaused",
                    "params": {"requestId": "abc"},
                })
                self.assertTrue(_wait_until(lambda: bool(received)))
        self.assertEqual(received, [{"requestId": "abc"}])

    def test_off_removes_handler(self):
        fake_ws = FakeWebSocket()
        received = []
        with _patch_websocket(fake_ws):
            with CDPEventListener("ws://fake") as listener:
                cb = received.append
                listener.on("Page.loadEventFired", cb)
                self.assertTrue(listener.off("Page.loadEventFired", cb))
                # 再 off 一次 (找不到) 應回 False
                self.assertFalse(listener.off("Page.loadEventFired", cb))
                fake_ws.push_dict({"method": "Page.loadEventFired", "params": {}})
                # 給點時間讓 _run 走過去；應該不會被派發
                time.sleep(0.1)
        self.assertEqual(received, [])

    def test_handler_exception_does_not_kill_loop(self):
        fake_ws = FakeWebSocket()
        good = []
        with _patch_websocket(fake_ws):
            with CDPEventListener("ws://fake") as listener:
                listener.on("X", lambda p: (_ for _ in ()).throw(RuntimeError("boom")))
                listener.on("X", lambda p: good.append(p))
                fake_ws.push_dict({"method": "X", "params": {"n": 1}})
                self.assertTrue(_wait_until(lambda: bool(good)))
                # 第二個事件也要照常派發
                fake_ws.push_dict({"method": "X", "params": {"n": 2}})
                self.assertTrue(_wait_until(lambda: len(good) >= 2))


class TestCDPEventListenerSend(unittest.TestCase):

    def test_send_round_trip(self):
        fake_ws = FakeWebSocket()
        with _patch_websocket(fake_ws):
            with CDPEventListener("ws://fake") as listener:
                # 在另一條 thread 上 send，主 thread 模擬伺服器回覆
                result_holder: dict = {}

                def call_send():
                    result_holder["value"] = listener.send(
                        "Network.enable", {"maxTotalBufferSize": 1024}, timeout=1.0
                    )

                t = threading.Thread(target=call_send, daemon=True)
                t.start()
                # 等到對方真的 send 到 ws 才回覆
                self.assertTrue(_wait_until(lambda: bool(fake_ws.sent)))
                sent_payload = json.loads(fake_ws.sent[-1])
                fake_ws.push_dict(
                    {"id": sent_payload["id"], "result": {"ok": True}}
                )
                t.join(timeout=1.0)
        self.assertEqual(result_holder["value"], {"ok": True})

    def test_send_propagates_cdp_error(self):
        fake_ws = FakeWebSocket()
        with _patch_websocket(fake_ws):
            with CDPEventListener("ws://fake") as listener:
                exc_holder: dict = {}

                def call_send():
                    try:
                        listener.send("Bad.method", timeout=1.0)
                    except CDPEventLoopError as e:
                        exc_holder["error"] = e

                t = threading.Thread(target=call_send, daemon=True)
                t.start()
                self.assertTrue(_wait_until(lambda: bool(fake_ws.sent)))
                sent_payload = json.loads(fake_ws.sent[-1])
                fake_ws.push_dict({
                    "id": sent_payload["id"],
                    "error": {"code": -32601, "message": "method not found"},
                })
                t.join(timeout=1.0)
        self.assertIn("error", exc_holder)

    def test_send_times_out(self):
        fake_ws = FakeWebSocket()
        with _patch_websocket(fake_ws):
            with CDPEventListener("ws://fake") as listener:
                with self.assertRaises(CDPEventLoopError):
                    listener.send("Slow.method", timeout=0.1)

    def test_send_before_start_raises(self):
        listener = CDPEventListener("ws://fake")
        with self.assertRaises(CDPEventLoopError):
            listener.send("Network.enable")


class TestResolveCdpWsUrl(unittest.TestCase):

    def test_prefers_debugger_address_via_json(self):
        driver = MagicMock()
        driver.capabilities = {
            "goog:chromeOptions": {"debuggerAddress": "127.0.0.1:9222"},
            "se:cdp": "ws://wrong",
        }
        fake_response = MagicMock()
        fake_response.read.return_value = json.dumps([
            {"type": "background_page", "webSocketDebuggerUrl": "ws://bg"},
            {"type": "page", "webSocketDebuggerUrl": "ws://page-1"},
        ]).encode("utf-8")
        fake_response.__enter__ = lambda self_=fake_response: self_
        fake_response.__exit__ = lambda *a: None
        with patch("urllib.request.urlopen", return_value=fake_response):
            self.assertEqual(resolve_cdp_ws_url(driver), "ws://page-1")

    def test_falls_back_to_se_cdp(self):
        driver = MagicMock()
        driver.capabilities = {"se:cdp": "ws://browser-level"}
        self.assertEqual(resolve_cdp_ws_url(driver), "ws://browser-level")

    def test_no_source_raises(self):
        driver = MagicMock()
        driver.capabilities = {}
        with self.assertRaises(CDPEventLoopError):
            resolve_cdp_ws_url(driver)

    def test_no_page_target_raises(self):
        driver = MagicMock()
        driver.capabilities = {
            "ms:edgeOptions": {"debuggerAddress": "127.0.0.1:9333"},
        }
        fake_response = MagicMock()
        fake_response.read.return_value = b"[]"
        fake_response.__enter__ = lambda self_=fake_response: self_
        fake_response.__exit__ = lambda *a: None
        with patch("urllib.request.urlopen", return_value=fake_response):
            with self.assertRaises(CDPEventLoopError):
                resolve_cdp_ws_url(driver)


if __name__ == "__main__":
    unittest.main()
