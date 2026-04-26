"""
測試常見外部依賴的最小 mock：SMTP（capture）/ OAuth（token issuer）/ S3（記憶體 KV）。
Lightweight mock services for tests:

- :class:`MockSmtpServer` — captures messages via :class:`socketserver.TCPServer`.
- :class:`MockOAuthServer` — HTTP server that issues fake bearer tokens.
- :class:`MockS3Storage` — purely in-memory bucket (no network), for code that
  takes a "storage" interface.
"""
from __future__ import annotations

import json
import secrets
import socketserver
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Callable, Dict, List, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException


class MockServiceError(WebRunnerException):
    """Raised when a mock service fails to start or respond."""


# ----- in-memory S3 ----------------------------------------------------------

@dataclass
class MockS3Storage:
    """In-memory key-value store mimicking S3 ``put_object`` / ``get_object``."""

    buckets: Dict[str, Dict[str, bytes]] = field(default_factory=dict)

    def create_bucket(self, name: str) -> None:
        self.buckets.setdefault(name, {})

    def put_object(self, bucket: str, key: str, body: bytes) -> None:
        if bucket not in self.buckets:
            raise MockServiceError(f"bucket {bucket!r} does not exist")
        if not isinstance(body, (bytes, bytearray)):
            raise MockServiceError("body must be bytes")
        self.buckets[bucket][key] = bytes(body)

    def get_object(self, bucket: str, key: str) -> bytes:
        try:
            return self.buckets[bucket][key]
        except KeyError as error:
            raise MockServiceError(f"object {key!r} not found in {bucket!r}") from error

    def list_objects(self, bucket: str) -> List[str]:
        return sorted(self.buckets.get(bucket, {}).keys())


# ----- SMTP capture ----------------------------------------------------------

_SMTP_OK = b"250 ok\r\n"


class _SmtpHandler(socketserver.StreamRequestHandler):

    def handle(self) -> None:  # pragma: no cover - exercised via integration paths
        server: Any = self.server  # type: ignore[assignment]
        self.wfile.write(b"220 mock SMTP\r\n")
        state: Dict[str, Any] = {"in_data": False, "lines": []}
        while True:
            line = self.rfile.readline()
            if not line:
                break
            decoded = line.decode("utf-8", errors="replace")
            if state["in_data"]:
                _handle_data_line(self, server, state, decoded)
            elif not _handle_command(self, decoded, state):
                break


def _handle_command(handler: Any, decoded: str, state: Dict[str, Any]) -> bool:
    """Process one command line; return False to close the connection."""
    upper = decoded.upper().strip()
    if upper == "QUIT":
        handler.wfile.write(b"221 bye\r\n")
        return False
    if upper == "DATA":
        handler.wfile.write(b"354 send data\r\n")
        state["in_data"] = True
    else:
        handler.wfile.write(_SMTP_OK)
    return True


def _handle_data_line(handler: Any, server: Any, state: Dict[str, Any], decoded: str) -> None:
    if decoded.strip() == ".":
        server.captured.append("".join(state["lines"]))
        state["lines"] = []
        state["in_data"] = False
        handler.wfile.write(b"250 queued\r\n")
    else:
        state["lines"].append(decoded)


class MockSmtpServer:
    """Capture-only SMTP server. Bind to ``127.0.0.1`` and call :meth:`start`."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0) -> None:
        self.host = host
        self.port = port
        self.captured: List[str] = []
        self._server: Optional[socketserver.TCPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> int:
        if self._server is not None:
            raise MockServiceError("SMTP server already started")
        srv = socketserver.TCPServer((self.host, self.port), _SmtpHandler)
        srv.captured = self.captured  # type: ignore[attr-defined]
        thread = threading.Thread(target=srv.serve_forever, daemon=True)
        thread.start()
        self._server = srv
        self._thread = thread
        self.port = srv.server_address[1]
        return self.port

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
            self._thread = None


# ----- OAuth token issuer ----------------------------------------------------

def _make_oauth_handler(server_state: Dict[str, Any]) -> Callable:

    class _OAuthRequestHandler(BaseHTTPRequestHandler):

        def log_message(self, format, *args):  # pylint: disable=redefined-builtin
            # ``format`` shadowing is required by BaseHTTPRequestHandler's API;
            # silence stdlib-driven access logging.
            return

        def _send(self, status: int, payload: Dict[str, Any]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):  # noqa: N802 - http.server convention
            if self.path == "/token":
                token = secrets.token_hex(16)
                server_state["issued"].append(token)
                self._send(200, {
                    "access_token": token,
                    "token_type": "Bearer",
                    "expires_in": 3600,
                })
                return
            self._send(404, {"error": "not_found"})

    return _OAuthRequestHandler


class MockOAuthServer:
    """Issues a fake bearer token from ``POST /token``."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0) -> None:
        self.host = host
        self.port = port
        self.issued: List[str] = []
        self._state: Dict[str, Any] = {"issued": self.issued}
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> str:
        if self._server is not None:
            raise MockServiceError("OAuth server already started")
        handler = _make_oauth_handler(self._state)
        srv = HTTPServer((self.host, self.port), handler)
        thread = threading.Thread(target=srv.serve_forever, daemon=True)
        thread.start()
        self._server = srv
        self._thread = thread
        self.port = srv.server_address[1]
        return f"http://{self.host}:{self.port}"  # NOSONAR — local mock

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
            self._thread = None
