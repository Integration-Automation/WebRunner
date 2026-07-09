"""
跑一個臨時 HTTP server,接 app 寄出的 webhook 並做斷言。
Common scenarios: payment-provider callback, third-party SaaS event
notification, your own backend → backend webhook. End-to-end tests need
to *receive* those calls before declaring success.

Uses stdlib ``http.server`` so there's no extra dependency. Runs in a
background thread, picks a free port automatically, and exposes:

* :class:`WebhookServer` — start/stop context manager
* :class:`ReceivedRequest` — captured request record
* assertion helpers: ``received_path``, ``received_with_header``,
  ``received_json_matching``
"""
from __future__ import annotations

import json
import socket
import threading
import time
from dataclasses import asdict, dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib.parse import parse_qs, urlsplit

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class WebhookReceiverError(WebRunnerException):
    """Raised on server start failure or failed assertion."""


# ---------- data --------------------------------------------------------

@dataclass
class ReceivedRequest:
    """One inbound HTTP request."""

    method: str
    path: str
    query: dict[str, list[str]] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    timestamp: float = field(default_factory=time.time)

    def body_text(self, encoding: str = "utf-8") -> str:
        return self.body.decode(encoding, errors="replace")

    def body_json(self) -> Any:
        try:
            return json.loads(self.body_text())
        except ValueError as error:
            raise WebhookReceiverError(
                f"body is not JSON ({error}): {self.body[:80]!r}"
            ) from error

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["body"] = self.body.decode("utf-8", errors="replace")
        return out


# ---------- handler factory --------------------------------------------

ResponseFn = Callable[[ReceivedRequest], dict[str, Any] | None]


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _build_handler(
    received: list[ReceivedRequest],
    lock: threading.Lock,
    response_fn: ResponseFn | None,
) -> type:
    class WebhookHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format: str, *args: Any) -> None:  # pylint: disable=redefined-builtin — match BaseHTTPRequestHandler signature
            web_runner_logger.debug("webhook " + (format % args))

        def _handle(self, method: str) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length > 0 else b""
            url_parts = urlsplit(self.path)
            request = ReceivedRequest(
                method=method,
                path=url_parts.path,
                query=parse_qs(url_parts.query),
                headers=dict(self.headers.items()),
                body=body,
            )
            with lock:
                received.append(request)
            response: dict[str, Any] = {
                "status": 200,
                "headers": {"Content-Type": "application/json"},
                "body": b'{"received":true}',
            }
            if response_fn is not None:
                try:
                    override = response_fn(request)
                except Exception as error:
                    web_runner_logger.warning(f"response_fn raised: {error!r}")
                    override = None
                if override:
                    response.update(override)
                    body = response.get("body")
                    if isinstance(body, str):
                        response["body"] = body.encode("utf-8")
            self.send_response(int(response["status"]))
            response_body = response.get("body") or b""
            if isinstance(response_body, str):
                response_body = response_body.encode("utf-8")
            for name, value in (response.get("headers") or {}).items():
                self.send_header(str(name), str(value))
            self.send_header("Content-Length", str(len(response_body)))
            self.end_headers()
            if response_body:
                self.wfile.write(response_body)

        # noinspection PyPep8Naming
        def do_GET(self) -> None: self._handle("GET")
        def do_POST(self) -> None: self._handle("POST")
        def do_PUT(self) -> None: self._handle("PUT")
        def do_PATCH(self) -> None: self._handle("PATCH")
        def do_DELETE(self) -> None: self._handle("DELETE")
        def do_OPTIONS(self) -> None: self._handle("OPTIONS")
    return WebhookHandler


# ---------- server ------------------------------------------------------

class WebhookServer:
    """Threaded HTTP server. Use as a context manager."""

    def __init__(
        self,
        *,
        host: str = "127.0.0.1",
        port: int | None = None,
        response_fn: ResponseFn | None = None,
    ) -> None:
        if not isinstance(host, str) or not host:
            raise WebhookReceiverError("host must be non-empty string")
        if port is not None and (port <= 0 or port >= 65536):
            raise WebhookReceiverError("port must be a valid TCP port")
        self._host = host
        self._port = port or _free_port()
        self._response_fn = response_fn
        self._received: list[ReceivedRequest] = []
        self._lock = threading.Lock()
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def base_url(self) -> str:
        # S5332 ok: this is a localhost test-fixture HTTP server with random
        # port, intentionally plain HTTP so callers can hit it without certs.
        return f"http://{self._host}:{self._port}"  # NOSONAR S5332 — intentional plain HTTP (localhost/dev-configured endpoint), not a security-sensitive transport

    def start(self) -> WebhookServer:
        if self._server is not None:
            raise WebhookReceiverError("server already started")
        handler_cls = _build_handler(
            self._received, self._lock, self._response_fn,
        )
        try:
            self._server = ThreadingHTTPServer((self._host, self._port), handler_cls)
        except OSError as error:
            raise WebhookReceiverError(
                f"failed to bind {self._host}:{self._port}: {error}"
            ) from error
        self._thread = threading.Thread(
            target=self._server.serve_forever, daemon=True, name="wr-webhook",
        )
        self._thread.start()
        web_runner_logger.info(f"webhook_receiver listening on {self.base_url}")
        return self

    def stop(self) -> None:
        if self._server is None:
            return
        self._server.shutdown()
        self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._server = None
        self._thread = None

    def __enter__(self) -> WebhookServer:
        return self.start()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()

    def received(self) -> list[ReceivedRequest]:
        with self._lock:
            return list(self._received)

    def clear(self) -> None:
        with self._lock:
            self._received.clear()

    def wait_for(
        self,
        predicate: Callable[[ReceivedRequest], bool],
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> ReceivedRequest:
        """Poll for a request matching ``predicate`` within ``timeout`` seconds."""
        if timeout <= 0:
            raise WebhookReceiverError("timeout must be > 0")
        if interval <= 0:
            raise WebhookReceiverError("interval must be > 0")
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for request in self.received():
                try:
                    if predicate(request):
                        return request
                except Exception as error:
                    web_runner_logger.warning(f"wait_for predicate raised: {error!r}")
            time.sleep(interval)
        raise WebhookReceiverError(
            f"no webhook matched within {timeout}s "
            f"(received {len(self.received())} requests)"
        )


# ---------- assertions -------------------------------------------------

def assert_received_path(
    server: WebhookServer,
    path: str,
    *,
    method: str | None = None,
    minimum: int = 1,
) -> int:
    """Assert at least ``minimum`` requests hit ``path``."""
    if not isinstance(path, str) or not path:
        raise WebhookReceiverError("path must be non-empty string")
    matches = [
        r for r in server.received()
        if r.path == path and (method is None or r.method == method)
    ]
    if len(matches) < minimum:
        raise WebhookReceiverError(
            f"expected >= {minimum} requests to {path!r}, got {len(matches)}"
        )
    return len(matches)


def assert_received_with_header(
    server: WebhookServer,
    header: str,
    value: str,
) -> ReceivedRequest:
    """Assert at least one request had ``header: value``."""
    if not header:
        raise WebhookReceiverError("header must be non-empty string")
    header_lower = header.lower()
    for request in server.received():
        for name, val in request.headers.items():
            if name.lower() == header_lower and val == value:
                return request
    raise WebhookReceiverError(
        f"no request had header {header}={value!r}"
    )


def assert_received_json_matching(
    server: WebhookServer,
    predicate: Callable[[Any], bool],
    *,
    description: str = "json predicate",
) -> ReceivedRequest:
    """Assert at least one JSON body satisfies ``predicate``."""
    for request in server.received():
        try:
            payload = request.body_json()
        except WebhookReceiverError:
            continue
        try:
            if predicate(payload):
                return request
        except Exception:  # nosec B112 — user predicate may legitimately raise; skip + continue
            continue
    raise WebhookReceiverError(
        f"no JSON webhook matched: {description}"
    )
