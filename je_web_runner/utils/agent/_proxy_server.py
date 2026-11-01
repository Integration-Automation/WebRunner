"""Bound the owned browser proxy's request workers and release each accepted client exactly once."""
from __future__ import annotations

from http.server import ThreadingHTTPServer
import socket
import threading
from typing import Any

from je_web_runner.utils.agent._proxy_handler import BrowserProxyHandler
from je_web_runner.utils.agent.types import AgentError
from je_web_runner.utils.agent._proxy_types import ProxyOwner


def _tcp_socket(value: Any) -> socket.socket:
    if not isinstance(value, socket.socket):
        raise AgentError("browser proxy accepts TCP sockets only")
    return value


class BrowserProxyServer(ThreadingHTTPServer):
    """A private IPv4 loopback endpoint with at most sixteen live request threads."""

    def __init__(self, owner: ProxyOwner) -> None:
        self.owner = owner
        self._slots = threading.BoundedSemaphore(16)
        super().__init__(("127.0.0.1", 0), BrowserProxyHandler)

    def process_request(self, request: Any, client_address: Any) -> None:
        """Refuse excess clients before creating their worker thread."""
        request = _tcp_socket(request)
        # pylint: disable-next=consider-using-with  # reason: its permit crosses into the accepted worker thread
        if not self._slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._slots.release()
            raise

    def process_request_thread(self, request: Any, client_address: Any) -> None:
        """Keep only this owner's accepted sockets in its retirement registry."""
        try:
            request = _tcp_socket(request)
            self.owner.retain_socket(request)
            super().process_request_thread(request, client_address)
        except AgentError:
            self.shutdown_request(request)
        finally:
            try:
                self.owner.release_socket(request)
            finally:
                self._slots.release()
