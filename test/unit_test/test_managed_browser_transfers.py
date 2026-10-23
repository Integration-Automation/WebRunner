"""Scoped transfers exercise owned loopback sockets and fake file inputs, never a browser or OS dialog."""
from contextlib import contextmanager
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
from unittest.mock import Mock

import pytest

from je_web_runner.utils.agent._browser_download import download_response
from je_web_runner.utils.agent._browser_upload import upload_bytes
from je_web_runner.utils.agent.network_policy import BrowserOriginPolicy
from je_web_runner.utils.agent.scoped_proxy import ScopedBrowserProxy
from je_web_runner.utils.agent.types import AgentError


@pytest.fixture
def origin():
    records = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            records.append((self.path, dict(self.headers)))
            if self.path in {"/redirect", "/outside", "/loop"}:
                destination = {"/redirect": "/file", "/outside": "http://blocked.invalid/file", "/loop": "/loop"}
                self.send_response(302)
                self.send_header("Location", destination[self.path])
                self.end_headers()
                return
            if self.path == "/truncated":
                self.send_response(200)
                self.send_header("Content-Length", "100")
                self.end_headers()
                self.wfile.write(b"short")
                return
            data = b"owned download"
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": .05}, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", records
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_download_follows_only_approved_redirects_with_url_scoped_private_cookies(origin):
    url, records = origin
    cookies = Mock(return_value=[{"name": "session", "value": "private-fixture"}])
    with ScopedBrowserProxy(BrowserOriginPolicy((url,))) as proxy:
        with download_response(proxy, url + "/redirect", cookies, 2) as response:
            assert response.read() == b"owned download"
            assert response.read() == b""
        assert not proxy._sockets
    assert [call.args[0] for call in cookies.call_args_list] == [url + "/redirect", url + "/file"]
    assert records[-1][1]["Cookie"] == "session=private-fixture"
    assert "Proxy-Authorization" not in records[-1][1]


def test_redirect_outside_origin_is_refused_before_cookie_lookup_or_connect(origin):
    url, records = origin
    cookies = Mock(return_value=[])
    with ScopedBrowserProxy(BrowserOriginPolicy((url,))) as proxy:
        with pytest.raises(AgentError, match="outside allowed origins"):
            with download_response(proxy, url + "/outside", cookies, 2):
                pytest.fail("unapproved redirect yielded a download")
        assert not proxy._sockets
    assert len(records) == 1
    cookies.assert_called_once_with(url + "/outside")


def test_redirect_count_and_chunk_sizes_are_bounded(origin):
    url, records = origin
    with ScopedBrowserProxy(BrowserOriginPolicy((url,))) as proxy:
        with pytest.raises(AgentError, match="redirect limit"):
            with download_response(proxy, url + "/loop", lambda _url: [], 2):
                pytest.fail("redirect loop yielded")
        assert len(records) == 6
        with download_response(proxy, url + "/file", lambda _url: [], 2) as response:
            for size in (-1, 0, True, 65537):
                with pytest.raises(AgentError, match="bounded read"):
                    response.read(size)
        assert not proxy._sockets


def test_download_size_limit_closes_owned_transport(origin, monkeypatch):
    from je_web_runner.utils.agent import _browser_download
    url, _records = origin
    monkeypatch.setattr(_browser_download, "MAX_DOWNLOAD", 3)
    with ScopedBrowserProxy(BrowserOriginPolicy((url,))) as proxy:
        with pytest.raises(AgentError, match="sixteen megabytes"):
            with download_response(proxy, url + "/file", lambda _url: [], 2) as response:
                response.read()
        assert not proxy._sockets


def test_declared_content_length_truncation_is_not_successful_eof(origin):
    url, _records = origin
    with ScopedBrowserProxy(BrowserOriginPolicy((url,))) as proxy:
        with download_response(proxy, url + "/truncated", lambda _url: [], 2) as response:
            assert response.read() == b"short"
            with pytest.raises(AgentError, match="incomplete"):
                response.read()
        assert not proxy._sockets


def test_invalid_cookie_headers_never_reach_origin(origin):
    url, records = origin
    with ScopedBrowserProxy(BrowserOriginPolicy((url,))) as proxy:
        with pytest.raises(AgentError, match="cookies are invalid"):
            with download_response(proxy, url + "/file", lambda _url: [{"name": "x", "value": "x\r\ninject"}], 2):
                pytest.fail("invalid cookie yielded")
    assert records == []


def test_retirement_aborts_only_owned_download_socket(origin):
    url, _records = origin
    proxy = ScopedBrowserProxy(BrowserOriginPolicy((url,)))
    proxy.start()
    try:
        with download_response(proxy, url + "/file", lambda _url: [], 2) as response:
            proxy.close()
            with pytest.raises(AgentError, match="not active"):
                response.read()
    finally:
        proxy.close()
    assert proxy.closed


@contextmanager
def file_scope(element):
    yield Mock()


def test_upload_sends_only_explicit_bytes_and_verifies_file_metadata():
    element = Mock()
    element.evaluate.side_effect = [True, [{"name": "report.bin", "size": 4}]]
    session = Mock()
    session.scope.side_effect = lambda _frame: file_scope(element)
    session._find.return_value = element
    result = upload_bytes(session, "#file", b"data", "report.bin", "")
    assert result == {"name": "report.bin", "bytes": 4, "sha256": hashlib.sha256(b"data").hexdigest()}
    element.set_input_files.assert_called_once_with({"name": "report.bin", "mimeType": "application/octet-stream",
                                                   "buffer": b"data"})


@pytest.mark.parametrize("name", ["../outside", "a\\b", "x\r\n", "x:stream", ""])
def test_upload_cannot_request_an_arbitrary_filename_or_path(name):
    session = Mock()
    with pytest.raises(AgentError):
        upload_bytes(session, "#file", b"data", name, "")
    session.scope.assert_not_called()


def test_upload_refuses_wrong_control_or_readback_without_repeating_effect():
    element = Mock()
    session = Mock()
    session.scope.side_effect = lambda _frame: file_scope(element)
    session._find.return_value = element
    element.evaluate.return_value = False
    with pytest.raises(AgentError, match="file input"):
        upload_bytes(session, "#not-file", b"data", "report.bin", "")
    element.set_input_files.assert_not_called()
    element.evaluate.side_effect = [True, []]
    with pytest.raises(AgentError, match="does not match"):
        upload_bytes(session, "#file", b"data", "report.bin", "")
    assert element.set_input_files.call_count == 1


@pytest.mark.parametrize("contents", [b"", bytearray(b"data"), "path/to/file", b"x" * (4 * 1024 * 1024 + 1)],
                         ids=["empty", "mutable", "path", "over-limit"])
def test_upload_rejects_unsupported_payload_before_element_lookup(contents):
    session = Mock()
    with pytest.raises(AgentError, match="four megabytes"):
        upload_bytes(session, "#file", contents, "report.bin", "")
    session.scope.assert_not_called()
