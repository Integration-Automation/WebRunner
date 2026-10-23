"""Bounded one-attempt HTTP(S) reads reuse browser cookies and the owned origin transport."""
from __future__ import annotations

from contextlib import contextmanager
from http.client import HTTPConnection, HTTPResponse, HTTPMessage
import socket
import ssl
import time
from typing import Any, Callable, Iterator
from urllib.parse import urljoin, urlsplit, urlunsplit

from je_web_runner.utils.agent.scoped_proxy import ScopedBrowserProxy
from je_web_runner.utils.agent.types import AgentError, positive

MAX_DOWNLOAD = 16 * 1024 * 1024
_REDIRECTS = frozenset({301, 302, 303, 307, 308})


def _remaining(deadline: float) -> float:
    result = deadline - time.monotonic()
    if result <= 0:
        raise AgentError("managed download deadline exhausted")
    return result


def _client_context() -> ssl.SSLContext:
    return ssl.create_default_context()


def _tls_socket(proxy: ScopedBrowserProxy, raw: socket.socket, host: str, deadline: float) -> ssl.SSLSocket:
    secured: ssl.SSLSocket | None = None
    try:
        secured = _client_context().wrap_socket(raw, server_hostname=host, do_handshake_on_connect=False)
        proxy.retain_socket(secured)
        proxy.release_socket(raw)  # wrap_socket transferred the descriptor; keep ownership of the new object.
        secured.settimeout(_remaining(deadline))
        secured.do_handshake()
        return secured
    except BaseException:  # reason: a partial TLS wrapper must never escape owned socket retirement
        proxy.release_socket(secured if secured is not None else raw)
        raise


def _cookie_pair(item: Any) -> str:
    if not isinstance(item, dict) or not all(isinstance(item.get(key), str) for key in ("name", "value")):
        raise AgentError("managed download cookies are invalid")
    part = item["name"] + "=" + item["value"]
    if "\r" in part or "\n" in part or len(part) > 8192:
        raise AgentError("managed download cookies are invalid")
    return part


def _cookie_header(values: Any) -> str:
    if not isinstance(values, list) or len(values) > 200:
        raise AgentError("managed download cookie scope exceeds its limit")
    result = "; ".join(_cookie_pair(item) for item in values)
    if not result.isascii() or len(result) > 65536:
        raise AgentError("managed download cookies exceed the header limit")
    return result


class BrowserDownload:
    """An owned response exposes bounded chunks only; it never accepts a filesystem path."""

    def __init__(self, proxy: ScopedBrowserProxy, connection: HTTPConnection,
                 transport: socket.socket, response: HTTPResponse, deadline: float) -> None:
        self._proxy, self._connection, self._transport = proxy, connection, transport
        self._response, self._deadline = response, deadline
        self._size = 0
        self._closed = False

    @property
    def headers(self) -> HTTPMessage:
        """Response metadata for complete-length verification; callers must keep cookie headers private."""
        return self._response.headers

    def read(self, size: int = 65536) -> bytes:
        """Read at most 64 KiB once, enforcing total bytes and rejecting late data."""
        self._require_read(size)
        if self._response.length == 0 or self._response.isclosed():
            if self._response.length not in {None, 0}:
                raise AgentError("managed download response is incomplete")
            return b""
        self._transport.settimeout(_remaining(self._deadline))
        data = self._response.read(size)
        self._proxy.require_active()
        _remaining(self._deadline)
        self._size += len(data)
        if self._size > MAX_DOWNLOAD:
            raise AgentError("managed download exceeds sixteen megabytes")
        if not data and self._response.length not in {None, 0}:
            raise AgentError("managed download response is incomplete")
        return data

    def _require_read(self, size: int) -> None:
        if self._closed or isinstance(size, bool) or not isinstance(size, int) or not 1 <= size <= 65536:
            raise AgentError("managed download requires an active bounded read")
        self._proxy.require_active()
        _remaining(self._deadline)

    def close(self) -> None:
        """Close only this response and retained transport, including partial transfers."""
        if self._closed:
            return
        self._closed = True
        try:
            self._response.close()
        finally:
            try:
                self._connection.close()
            finally:
                self._proxy.release_socket(self._transport)


def _request(proxy: ScopedBrowserProxy, url: str, cookies: list[dict], deadline: float) -> BrowserDownload:
    parsed = urlsplit(url)
    headers = {"Accept-Encoding": "identity", "Connection": "close", "Cookie": _cookie_header(cookies)}
    connection = HTTPConnection(str(parsed.hostname), parsed.port, timeout=_remaining(deadline))
    transport = proxy.open_upstream(url)
    try:
        if parsed.scheme == "https":
            transport = _tls_socket(proxy, transport, str(parsed.hostname), deadline)
        transport.settimeout(_remaining(deadline))
        connection.sock = transport
        path = urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
        connection.request("GET", path, headers=headers)
        response = connection.getresponse()
        return BrowserDownload(proxy, connection, transport, response, deadline)
    except BaseException:  # reason: every partial request owns and must release only its new connection
        connection.close()
        proxy.release_socket(transport)
        raise


@contextmanager
def download_response(proxy: ScopedBrowserProxy, url: str, cookies: Callable[[str], list[dict]],
                      timeout: float) -> Iterator[BrowserDownload]:
    """Check each redirect before cookie lookup/connect; never retry a failed GET or mutate browser cookies."""
    positive(timeout, "download timeout")
    deadline = time.monotonic() + timeout
    for attempt in range(6):
        proxy.policy.require(url)
        _remaining(deadline)
        response = _request(proxy, url, cookies(url), deadline)
        try:
            status = response._response.status  # pylint: disable=protected-access
            if status in _REDIRECTS:
                location = response.headers.get("Location")
                if not location or attempt == 5:
                    raise AgentError("managed download redirect limit or target is invalid")
                url = urljoin(url, location)
                continue
            if status != 200:
                raise AgentError("managed download response is not a complete success")
            if response.headers.get("Content-Encoding", "identity").lower() not in {"", "identity"}:
                raise AgentError("managed download content encoding is unsupported")
            yield response
            return
        finally:
            response.close()
