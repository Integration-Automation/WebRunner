"""Owned TLS fixtures verify trust, hostname checks and retirement without browser or system trust changes."""
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import ssl
import threading
from unittest.mock import Mock

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
import pytest

from je_web_runner.utils.agent import _browser_download
from je_web_runner.utils.agent.network_policy import BrowserOriginPolicy
from je_web_runner.utils.agent.scoped_proxy import ScopedBrowserProxy
from je_web_runner.utils.agent.types import AgentError


@pytest.fixture
def tls_origin(tmp_path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "owned fixture")])
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(hours=1))
            .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), False)
            .sign(key, hashes.SHA256()))
    cert_path, key_path = tmp_path / "cert.pem", tmp_path / "key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                          serialization.NoEncryption()))
    records = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            records.append(dict(self.headers))
            self.send_response(200)
            self.send_header("Content-Length", "4")
            self.end_headers()
            self.wfile.write(b"safe")

        def log_message(self, *_args):
            return

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert_path, key_path)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": .05}, daemon=True)
    thread.start()
    try:
        yield server.server_port, cert_path, records
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_untrusted_certificate_rejected_before_sending_cookies(tls_origin):
    port, _cert, records = tls_origin
    url = f"https://127.0.0.1:{port}"
    with ScopedBrowserProxy(BrowserOriginPolicy((url,))) as proxy:
        with pytest.raises(ssl.SSLCertVerificationError):
            with _browser_download.download_response(proxy, url, Mock(return_value=[{"name": "x", "value": "private"}]), 2):
                pytest.fail("untrusted TLS yielded")
        assert not proxy._sockets
    assert records == []


def test_trusted_tls_checks_hostname_and_retains_only_owned_socket(tls_origin, monkeypatch):
    port, cert, records = tls_origin
    monkeypatch.setattr(_browser_download, "_client_context", lambda: ssl.create_default_context(cafile=str(cert)))
    url = f"https://127.0.0.1:{port}"
    wrong_host = f"https://localhost:{port}"
    with ScopedBrowserProxy(BrowserOriginPolicy((url, wrong_host))) as proxy:
        # Resolve the test hostname to the owned IPv4 listener; avoid Windows IPv6 fallback delays.
        connect = proxy.open_upstream
        monkeypatch.setattr(proxy, "open_upstream", lambda target: connect(target.replace("localhost", "127.0.0.1")))
        with pytest.raises(ssl.SSLCertVerificationError):
            with _browser_download.download_response(proxy, wrong_host, lambda _url: [], 2):
                pytest.fail("wrong hostname yielded")
        assert not proxy._sockets
        with _browser_download.download_response(proxy, url, lambda _url: [], 2) as response:
            assert response.read(1) == b"s"
            assert any(isinstance(item, ssl.SSLSocket) for item in proxy._sockets)
            proxy.close()
            with pytest.raises(AgentError, match="not active"):
                response.read()
    assert len(records) == 1
    assert not proxy._sockets
