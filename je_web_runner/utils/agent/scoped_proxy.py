"""Own an authenticated loopback proxy whose every destination is checked against a frozen origin policy."""
from __future__ import annotations

import base64
import hmac
import secrets
import socket
import threading
from urllib.parse import urlsplit

from je_web_runner.utils.agent.network_policy import BrowserOriginPolicy
from je_web_runner.utils.agent._proxy_server import BrowserProxyServer
from je_web_runner.utils.agent.types import AgentError
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


def _connect(host: str, port: int) -> socket.socket:
    return socket.create_connection((host, port), timeout=10)


def _close_socket(connection: socket.socket) -> None:
    try:
        connection.shutdown(socket.SHUT_RDWR)
    except OSError:
        web_runner_logger.debug("owned browser proxy socket is already shut down")
    connection.close()


class ScopedBrowserProxy:
    """A single-lifetime private network owner; construction is inert and close never affects foreign sockets."""

    def __init__(self, policy: BrowserOriginPolicy) -> None:
        if not isinstance(policy, BrowserOriginPolicy):
            raise AgentError("browser proxy requires a reviewed origin policy")
        self._policy = policy
        self._lock = threading.RLock()
        self._server: BrowserProxyServer | None = None
        self._thread: threading.Thread | None = None
        self._retired = False
        self._sockets: set[socket.socket] = set()
        self._token = secrets.token_urlsafe(32)

    @property
    def policy(self) -> BrowserOriginPolicy:
        """Return immutable origin grants without revealing connection credentials."""
        return self._policy

    @property
    def closed(self) -> bool:
        """Whether this owner has no retained listener awaiting retirement proof."""
        with self._lock:
            return self._server is None

    def start(self) -> None:
        """Bind only loopback on an ephemeral port, without installing or launching a browser."""
        with self._lock:
            if self._retired:
                raise AgentError("browser proxy is retired")
            if self._server is not None:
                return
            self._server = BrowserProxyServer(self)
            self._thread = threading.Thread(target=self._server.serve_forever, kwargs={"poll_interval": .05},
                                            name="WebRunnerScopedProxy", daemon=True)
            try:
                self._thread.start()
            except BaseException:
                self._server.server_close()
                self._server, self._thread = None, None
                raise

    def browser_proxy(self) -> dict[str, str]:
        """Return private SDK configuration; callers must not log or expose it to task/model data."""
        with self._lock:
            if self._server is None or self._retired:
                raise AgentError("browser proxy is not active")
            return {"server": f"http://127.0.0.1:{self._server.server_port}",
                    "username": "webrunner", "password": self._token, "bypass": "<-loopback>"}

    def authenticates(self, values: list[str] | None) -> bool:
        """Check one proxy-only Basic header without forwarding or logging it."""
        if values is None or len(values) != 1:
            return False
        parts = values[0].split(None, 1)
        if len(parts) != 2 or parts[0].lower() != "basic":
            return False
        expected = base64.b64encode(("webrunner:" + self._token).encode("utf-8"))
        return hmac.compare_digest(parts[1].encode("utf-8"), expected)

    def open_upstream(self, url: str) -> socket.socket:
        """Connect once to a reviewed origin and fence late resolution against retirement."""
        self._policy.require(url)
        with self._lock:
            if self._retired or self._server is None:
                raise AgentError("browser proxy is not active")
        parsed = urlsplit(url)
        port = parsed.port if parsed.port is not None else (443 if parsed.scheme == "https" else 80)
        connection = _connect(str(parsed.hostname), port)
        try:
            self.retain_socket(connection)
            return connection
        except BaseException:
            _close_socket(connection)
            raise

    def retain_socket(self, connection: socket.socket) -> None:
        """Register only a socket explicitly opened or accepted for this owner."""
        with self._lock:
            if self._retired:
                _close_socket(connection)
                raise AgentError("browser proxy is retired")
            self._sockets.add(connection)

    def release_socket(self, connection: socket.socket) -> None:
        """Close a retained socket; another owner's handle is never closed."""
        with self._lock:
            if connection not in self._sockets:
                return
            self._sockets.remove(connection)
        _close_socket(connection)

    def close(self) -> None:
        """Retire the listener and abort all owned connections; late connects cannot send new payloads."""
        with self._lock:
            self._retired = True
            server, thread = self._server, self._thread
            sockets = tuple(self._sockets)
            self._sockets.clear()
        for connection in sockets:
            _close_socket(connection)
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=2)
            if thread.is_alive():
                raise AgentError("browser proxy listener did not retire")
        with self._lock:
            self._server, self._thread = None, None

    def __enter__(self) -> ScopedBrowserProxy:
        self.start()
        return self

    def __exit__(self, *_error: object) -> None:
        self.close()
