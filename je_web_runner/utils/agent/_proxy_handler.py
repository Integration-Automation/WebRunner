"""Check every HTTP authority and HTTPS CONNECT before one bounded, non-retrying upstream operation."""
from __future__ import annotations

import http.client
from http.server import BaseHTTPRequestHandler
import re
import select
import socket
import time
from typing import Any, cast
from urllib.parse import urlsplit, urlunsplit

from je_web_runner.utils.agent.types import AgentError
from je_web_runner.utils.agent._proxy_types import ProxyOwner, ProxyListener
from je_web_runner.utils.logging.loggin_instance import web_runner_logger

MAX_UPLOAD = 8 * 1024 * 1024
MAX_RESPONSE = 64 * 1024 * 1024
_HOP_HEADERS = frozenset({"proxy-authorization", "proxy-authenticate", "proxy-connection", "connection",
                          "keep-alive", "te", "trailer", "transfer-encoding", "upgrade", "content-length"})


def _check_headers(items: list[tuple[str, str]]) -> None:
    for key, value in items:
        if re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", key) is None or "\r" in value or "\n" in value:
            raise AgentError("ambiguous proxy headers are not permitted")


def _headers(items: list[tuple[str, str]], *, host: str = "") -> list[tuple[str, str]]:
    _check_headers(items)
    excluded = set(_HOP_HEADERS)
    for key, value in items:
        if key.lower() == "connection":
            excluded.update(part.strip().lower() for part in value.split(","))
    if host:
        excluded.add("host")
    result = [(key, value) for key, value in items if key.lower() not in excluded]
    if host:
        result.append(("Host", host))
    result.append(("Connection", "close"))
    return result


class BrowserProxyHandler(BaseHTTPRequestHandler):
    """The private proxy accepts no ambient identity, upstream retries or arbitrary transport settings."""

    timeout = 10.0
    protocol_version = "HTTP/1.1"

    def __init__(self, request: socket.socket, client_address: Any, server: Any) -> None:
        self._reply_started = False
        super().__init__(request, client_address, server)

    @property
    def owner(self) -> ProxyOwner:
        """The one network owner assigned by the listener, never a request-selected resource."""
        return cast(ProxyListener, self.server).owner

    # pylint: disable-next=redefined-builtin  # reason: preserve the stdlib keyword parameter contract
    def log_message(self, format: str, *args: Any) -> None:
        """Do not log URL paths, request bodies, headers or proxy credentials."""
        return

    def _failure(self, status: int, message: str) -> None:
        self.close_connection = True
        if not self._reply_started:
            try:
                self.send_error(status, message)
            except OSError as error:
                web_runner_logger.debug("owned proxy client closed during refusal (%s)", type(error).__name__)

    def _authorized(self) -> bool:
        if not self.owner.authenticates(self.headers.get_all("Proxy-Authorization")):
            self.send_response(407)
            self.send_header("Proxy-Authenticate", 'Basic realm="WebRunner scoped browser"')
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True
            return False
        if sum(len(key) + len(value) for key, value in self.headers.items()) > 65536:
            self.send_error(431, "proxy headers exceed limit")
            return False
        return True

    def _body(self) -> bytes | None:
        if self.headers.get("Upgrade") is not None:
            self.send_error(501, "protocol upgrades are not supported")
            return None
        if self.headers.get("Transfer-Encoding") is not None:
            self.send_error(501, "streaming uploads are not supported")
            return None
        lengths = self.headers.get_all("Content-Length", [])
        if len(lengths) > 1 or (lengths and not lengths[0].isdigit()):
            self.send_error(400, "invalid upload length")
            return None
        size = int(lengths[0]) if lengths else 0
        if size > MAX_UPLOAD:
            self.send_error(413, "upload exceeds limit")
            return None
        body = self.rfile.read(size)
        if len(body) != size:
            raise AgentError("proxy upload ended before its declared length")
        return body

    def _destination(self, url: str) -> tuple[str, str, int, str]:
        origin = self.owner.policy.require(url)
        parsed = urlsplit(url)
        scheme = parsed.scheme
        port = parsed.port or (443 if scheme == "https" else 80)
        return origin.split("://", 1)[1], str(parsed.hostname), port, scheme

    def _forward(self) -> None:
        if not self._authorized():
            return
        upstream: socket.socket | None = None
        connection: http.client.HTTPConnection | None = None
        try:
            authority, host, port, scheme = self._destination(self.path)
            if scheme != "http":
                raise AgentError("HTTPS requests require CONNECT")
            body = self._body()
            if body is None:
                return
            upstream = self.owner.open_upstream(self.path)
            connection = http.client.HTTPConnection(host, port, timeout=10)
            connection.sock = upstream
            parsed = urlsplit(self.path)
            path = urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
            headers = dict(_headers(list(self.headers.items()), host=authority))
            connection.request(self.command, path, body=body, headers=headers)
            response = connection.getresponse()
            self._response(response)
        except AgentError:
            self._failure(403, "proxy destination or state refused")
        except (OSError, http.client.HTTPException, ValueError):
            self._failure(502, "upstream operation failed")
        finally:
            self.close_connection = True
            if connection is not None:
                connection.close()
            if upstream is not None:
                self.owner.release_socket(upstream)

    def _response(self, response: http.client.HTTPResponse) -> None:
        if response.status == 101:
            raise AgentError("protocol upgrades are not supported")
        headers = _headers(response.getheaders())
        self._reply_started = True
        self.send_response(response.status)
        for key, value in headers:
            self.send_header(key, value)
        has_body = self.command != "HEAD" and response.status not in {204, 304}
        if has_body:
            self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        if not has_body:
            return
        total, deadline = 0, time.monotonic() + 30
        while True:
            chunk = response.read1(65536)
            total += len(chunk)
            if total > MAX_RESPONSE or time.monotonic() > deadline:
                raise AgentError("proxy response exceeds its transfer bound")
            if not chunk:
                self.wfile.write(b"0\r\n\r\n")
                return
            self.wfile.write(f"{len(chunk):x}\r\n".encode("ascii") + chunk + b"\r\n")

    def do_CONNECT(self) -> None:  # pylint: disable=invalid-name  # reason: stdlib HTTP verb dispatch contract
        """Check one exact HTTPS authority before relaying opaque TLS bytes."""
        if not self._authorized():
            return
        upstream: socket.socket | None = None
        try:
            parsed = urlsplit("https://" + self.path)
            if parsed.path or parsed.query or parsed.fragment or parsed.port is None:
                raise AgentError("CONNECT requires an exact host and port")
            self._destination("https://" + self.path)
            upstream = self.owner.open_upstream("https://" + self.path)
            self._reply_started = True
            self.send_response(200, "Connection established")
            self.end_headers()
            self.wfile.flush()
            _relay(self.connection, upstream)
        except AgentError:
            self._failure(403, "proxy destination or state refused")
        except (OSError, ValueError):
            self._failure(502, "upstream connection failed")
        finally:
            self.close_connection = True
            if upstream is not None:
                self.owner.release_socket(upstream)

    do_GET = _forward
    do_HEAD = _forward
    do_POST = _forward
    do_PUT = _forward
    do_PATCH = _forward
    do_DELETE = _forward
    do_OPTIONS = _forward


def _relay(client: socket.socket, upstream: socket.socket) -> None:
    connections = (client, upstream)
    for connection in connections:
        connection.settimeout(1)
    while True:
        ready, _, _ = select.select(connections, [], [], .5)
        for incoming in ready:
            chunk = incoming.recv(65536)
            if not chunk:
                return
            outgoing = upstream if incoming is client else client
            outgoing.sendall(chunk)
