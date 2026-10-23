"""Owned loopback origin proxy tests never launch browsers or contact external hosts."""
import base64
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
from urllib.parse import urlsplit

import pytest


@pytest.fixture
def origin():
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append((self.path, dict(self.headers)))
            self.send_response(302 if self.path == "/redirect" else 200)
            if self.path == "/redirect":
                self.send_header("Location", "http://blocked.invalid/final")
            self.send_header("Set-Cookie", "one=1; Path=/")
            self.send_header("Set-Cookie", "two=2; Path=/")
            self.end_headers()
            self.wfile.write(b"fixture")

        def do_POST(self):
            payload = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            requests.append((self.path, payload))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": .05}, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(1)


def request(proxy, url, *, method="GET", body=None, headers=None, authenticated=True):
    settings = proxy.browser_proxy()
    address = urlsplit(settings["server"])
    connection = http.client.HTTPConnection(address.hostname, address.port, timeout=3)
    values = dict(headers or {})
    if authenticated:
        credential = (settings["username"] + ":" + settings["password"]).encode("utf-8")
        values["Proxy-Authorization"] = "Basic " + base64.b64encode(credential).decode("ascii")
    try:
        connection.request(method, url, body=body, headers=values)
        response = connection.getresponse()
        return response.status, response.getheaders(), response.read()
    finally:
        connection.close()


def test_proxy_is_inert_until_start_and_requires_authentication(origin):
    from je_web_runner.utils.agent.network_policy import BrowserOriginPolicy
    from je_web_runner.utils.agent.scoped_proxy import ScopedBrowserProxy
    url, seen = origin
    proxy = ScopedBrowserProxy(BrowserOriginPolicy((url,)))
    assert proxy.closed is True
    proxy.start()
    try:
        assert request(proxy, url, authenticated=False)[0] == 407
        assert seen == []
        assert request(proxy, url)[0] == 200
    finally:
        proxy.close()
    assert proxy.closed is True


def test_every_redirect_destination_is_checked_before_connecting(origin, monkeypatch):
    from je_web_runner.utils.agent.network_policy import BrowserOriginPolicy
    from je_web_runner.utils.agent.scoped_proxy import ScopedBrowserProxy
    from je_web_runner.utils.agent import scoped_proxy
    url, seen = origin
    connections = []
    connect = scoped_proxy._connect
    monkeypatch.setattr(scoped_proxy, "_connect", lambda host, port: (
        connections.append((host, port)), connect(host, port))[-1])
    with ScopedBrowserProxy(BrowserOriginPolicy((url,))) as proxy:
        status, headers, _body = request(proxy, url + "/redirect")
        assert status == 302
        location = next(value for key, value in headers if key.lower() == "location")
        assert request(proxy, location)[0] == 403
        assert len(connections) == 1 and len(seen) == 1


def test_proxy_preserves_cookies_and_payload_but_strips_proxy_credentials(origin):
    from je_web_runner.utils.agent.network_policy import BrowserOriginPolicy
    from je_web_runner.utils.agent.scoped_proxy import ScopedBrowserProxy
    url, seen = origin
    with ScopedBrowserProxy(BrowserOriginPolicy((url,))) as proxy:
        status, headers, body = request(proxy, url + "/read", headers={"Host": "wrong.invalid"})
        assert status == 200 and body == b"fixture"
        assert len([value for key, value in headers if key.lower() == "set-cookie"]) == 2
        assert "Proxy-Authorization" not in seen[0][1]
        assert seen[0][1]["Host"] == urlsplit(url).netloc
        assert request(proxy, url + "/write", method="POST", body=b"private fixture")[2] == b"private fixture"
        assert seen[-1][1] == b"private fixture"


def test_chunked_uploads_are_refused_before_an_upstream_effect(origin):
    from je_web_runner.utils.agent.network_policy import BrowserOriginPolicy
    from je_web_runner.utils.agent.scoped_proxy import ScopedBrowserProxy
    url, seen = origin
    with ScopedBrowserProxy(BrowserOriginPolicy((url,))) as proxy:
        assert request(proxy, url, method="POST", headers={"Transfer-Encoding": "chunked"})[0] == 501
        assert seen == []


def test_plain_http_upgrade_is_refused_before_contacting_the_origin(origin):
    from je_web_runner.utils.agent.network_policy import BrowserOriginPolicy
    from je_web_runner.utils.agent.scoped_proxy import ScopedBrowserProxy
    url, seen = origin
    with ScopedBrowserProxy(BrowserOriginPolicy((url,))) as proxy:
        assert request(proxy, url, headers={"Upgrade": "websocket", "Connection": "Upgrade"})[0] == 501
        assert seen == []


def test_incomplete_transfer_cannot_be_reported_as_a_complete_response(origin, monkeypatch):
    from je_web_runner.utils.agent.network_policy import BrowserOriginPolicy
    from je_web_runner.utils.agent.scoped_proxy import ScopedBrowserProxy
    from je_web_runner.utils.agent import _proxy_handler
    url, _seen = origin
    monkeypatch.setattr(_proxy_handler, "MAX_RESPONSE", 4)
    with ScopedBrowserProxy(BrowserOriginPolicy((url,))) as proxy:
        with pytest.raises(http.client.IncompleteRead):
            request(proxy, url)


def test_release_does_not_close_foreign_sockets(origin):
    import socket
    from je_web_runner.utils.agent.network_policy import BrowserOriginPolicy
    from je_web_runner.utils.agent.scoped_proxy import ScopedBrowserProxy
    url, _seen = origin
    left, right = socket.socketpair()
    try:
        with ScopedBrowserProxy(BrowserOriginPolicy((url,))) as proxy:
            proxy.release_socket(left)
            right.sendall(b"foreign")
            assert left.recv(7) == b"foreign"
    finally:
        left.close()
        right.close()


def test_connect_checks_scheme_and_keeps_tls_bytes_opaque():
    import socketserver
    from je_web_runner.utils.agent.network_policy import BrowserOriginPolicy
    from je_web_runner.utils.agent.scoped_proxy import ScopedBrowserProxy

    class Echo(socketserver.BaseRequestHandler):
        def handle(self):
            self.request.settimeout(2)
            self.request.sendall(self.request.recv(32))

    echo = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Echo)
    thread = threading.Thread(target=echo.serve_forever, kwargs={"poll_interval": .05}, daemon=True)
    thread.start()
    try:
        authority = "127.0.0.1:" + str(echo.server_address[1])
        with ScopedBrowserProxy(BrowserOriginPolicy(("https://" + authority,))) as proxy:
            settings = proxy.browser_proxy()
            address = urlsplit(settings["server"])
            credential = base64.b64encode((settings["username"] + ":" + settings["password"]).encode()).decode()
            connection = http.client.HTTPConnection(address.hostname, address.port, timeout=3)
            connection.set_tunnel("127.0.0.1", echo.server_address[1], headers={"Proxy-Authorization": "Basic " + credential})
            try:
                connection.connect()
                connection.sock.sendall(b"opaque fixture")
                assert connection.sock.recv(32) == b"opaque fixture"
            finally:
                connection.close()
            assert request(proxy, "http://" + authority)[0] == 403
    finally:
        echo.shutdown()
        echo.server_close()
        thread.join(1)


def test_close_fences_a_late_connect_and_does_not_reuse_its_credential_generation(origin, monkeypatch):
    import socket
    from je_web_runner.utils.agent import AgentError, scoped_proxy
    from je_web_runner.utils.agent.network_policy import BrowserOriginPolicy
    from je_web_runner.utils.agent.scoped_proxy import ScopedBrowserProxy
    url, _seen = origin
    left, right = socket.socketpair()
    entered, release = threading.Event(), threading.Event()
    errors = []

    def connect(_host, _port):
        entered.set()
        assert release.wait(1)
        return left

    monkeypatch.setattr(scoped_proxy, "_connect", connect)
    proxy = ScopedBrowserProxy(BrowserOriginPolicy((url,)))
    proxy.start()

    def late():
        try:
            proxy.open_upstream(url)
        except AgentError as error:
            errors.append(error)

    thread = threading.Thread(target=late)
    thread.start()
    try:
        assert entered.wait(1)
        proxy.close()
        release.set()
        thread.join(1)
        assert not thread.is_alive() and len(errors) == 1
        assert left.fileno() == -1
        with pytest.raises(AgentError, match="retired"):
            proxy.start()
    finally:
        release.set()
        thread.join(1)
        proxy.close()
        left.close()
        right.close()
