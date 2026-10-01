"""
The async executor on a real headless Chromium (async Playwright): concurrent users kept
apart, tabs, WebSocket frames, and ``--parallel-mode async``. Skips without Playwright.
"""
import asyncio
import base64
import hashlib
import json
import socket
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from je_web_runner.utils.async_executor.executor import AsyncExecutor
from je_web_runner.utils.cli.cli_main import main
from je_web_runner.utils.run_ledger.ledger import failed_files

_WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def _page(body: str) -> bytes:
    return f"<html><head><title>async test</title></head><body>{body}</body></html>".encode("utf-8")


class _Handler(BaseHTTPRequestHandler):
    ws_port = 0

    def do_GET(self):  # noqa: N802 — http.server naming
        if self.path.startswith("/login"):
            user = self.path.split("user=")[-1]
            body = _page(f"<script>document.cookie = 'user={user}'</script><p id='out'>hi {user}</p>")
        elif self.path == "/whoami":
            body = _page("<p id='out'></p><script>document.getElementById('out').textContent = document.cookie"
                         "</script>")
        else:
            body = _page(f"<p id='out'>waiting</p><script>const ws = new WebSocket('ws://127.0.0.1:{self.ws_port}/');"
                         "ws.onmessage = (e) => { document.getElementById('out').textContent = e.data; };</script>")
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        return


def _serve_websocket(server: socket.socket) -> None:
    """Accept WebSocket connections; send each one text frame and keep it open briefly."""
    while True:
        try:
            connection, _address = server.accept()
        except OSError:
            return
        request = connection.recv(4096).decode("latin-1")
        key = next(line.split(":", 1)[1].strip() for line in request.split("\r\n")
                   if line.lower().startswith("sec-websocket-key:"))
        accept = base64.b64encode(hashlib.sha1((key + _WS_GUID).encode(), usedforsecurity=False).digest()).decode()
        connection.sendall(("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                            f"Sec-WebSocket-Accept: {accept}\r\n\r\n").encode())
        payload = b"hello from the server"
        connection.sendall(bytes([0x81, len(payload)]) + payload)
        threading.Timer(5, connection.close).start()


class TestAsyncExecutorRealBrowser(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        try:
            import playwright.async_api  # noqa: F401
        except ImportError as error:
            raise unittest.SkipTest(f"Playwright is not installed: {error!r}")
        cls.ws = socket.socket()
        cls.ws.bind(("127.0.0.1", 0))
        cls.ws.listen()
        threading.Thread(target=_serve_websocket, args=(cls.ws,), daemon=True).start()
        _Handler.ws_port = cls.ws.getsockname()[1]
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.server.server_address[1]}"  # NOSONAR S5332 — local test server

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.ws.close()

    def _run_many(self, lists, concurrency):
        async def go():
            async with AsyncExecutor() as runner:
                return await runner.run_many(lists, concurrency)
        try:
            return asyncio.run(go())
        except Exception as error:  # no Chromium for Playwright here
            if "Executable doesn't exist" in str(error):
                self.skipTest(f"Playwright's Chromium is not installed: {error!r}")
            raise

    def _user(self, name):
        return [["WR_apw_goto", {"url": f"{self.url}/login?user={name}"}],
                ["WR_apw_evaluate", {"script": "Date.now()"}],
                ["WR_apw_sleep", [1]],
                ["WR_apw_evaluate", {"script": "Date.now()"}],
                ["WR_apw_goto", {"url": f"{self.url}/whoami"}],
                ["WR_apw_assert_text", {"selector": "#out", "expected": f"user={name}"}]]

    def test_concurrent_users_are_kept_apart(self):
        results = self._run_many([self._user("alice"), self._user("bob"), self._user("carol")], concurrency=3)
        for record, failed in results:
            self.assertEqual(failed, [], record)
        texts = [list(record.values())[-1] for record, _failed in results]
        self.assertEqual(texts, ["user=alice", "user=bob", "user=carol"])
        # Each list timed its 1 s sleep in the page; run at once, the three windows overlap.
        windows = [(list(record.values())[1], list(record.values())[3]) for record, _failed in results]
        self.assertLess(max(start for start, _end in windows), min(end for _start, end in windows))

    def test_tabs_and_sync_commands_in_one_list(self):
        [(record, failed)] = self._run_many([[
            ["WR_apw_goto", {"url": f"{self.url}/login?user=dave"}],
            ["WR_apw_new_page", {"url": f"{self.url}/whoami"}],
            ["WR_apw_text", {"selector": "#out"}],
            ["WR_apw_switch_to_page", [0]],
            ["WR_apw_title"],
            ["len", [[1, 2]]],
        ]], concurrency=1)
        self.assertEqual(failed, [], record)
        values = list(record.values())
        self.assertEqual(values[1], 1)
        self.assertEqual(values[2], "user=dave")  # the new tab is the same user
        self.assertEqual(values[4:], ["async test", 2])

    def test_websocket_frames(self):
        [(record, failed)] = self._run_many([[
            ["WR_apw_goto", {"url": f"{self.url}/socket"}],
            ["WR_apw_wait_for_websocket_message", {"contains": "hello", "timeout": 10}],
            ["WR_apw_websocket_messages", {"direction": "received"}],
            ["WR_apw_assert_text", {"selector": "#out", "expected": "hello from the server"}],
        ]], concurrency=1)
        self.assertEqual(failed, [], record)
        self.assertEqual(list(record.values())[2][0]["payload"], "hello from the server")

    def test_cli_parallel_mode_async(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("erin", "frank"):
                Path(tmp, f"{name}.json").write_text(json.dumps(self._user(name)), encoding="utf-8")
            ledger = str(Path(tmp, "ledger.out"))
            with patch("builtins.print"):
                main(["-d", tmp, "--parallel", "2", "--parallel-mode", "async", "--ledger", ledger])
            self.assertEqual(failed_files(ledger), [])
            self.assertEqual(len(json.loads(Path(ledger).read_text(encoding="utf-8"))["runs"]), 2)


if __name__ == "__main__":
    unittest.main()
