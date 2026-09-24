"""Unit tests for je_web_runner.utils.tls_cipher_audit."""
import unittest

from je_web_runner.utils.tls_cipher_audit.audit import (
    TlsCipherAuditError,
    TlsHandshakeReport,
    assert_cipher_safe,
    assert_modern_tls,
    assert_subject_matches,
    handshake,
)


class TestHandshakeArgs(unittest.TestCase):

    def test_bad_host(self):
        with self.assertRaises(TlsCipherAuditError):
            handshake("")

    def test_bad_port(self):
        with self.assertRaises(TlsCipherAuditError):
            handshake("example.com", port=99999)

    def test_bad_timeout(self):
        with self.assertRaises(TlsCipherAuditError):
            handshake("example.com", timeout=0)


class TestModernTls(unittest.TestCase):

    def test_pass(self):
        assert_modern_tls(TlsHandshakeReport(host="x", version="TLSv1.3"))

    def test_fail(self):
        tls_handshake_report = TlsHandshakeReport(host="x", version="TLSv1.0")
        with self.assertRaises(TlsCipherAuditError):
            assert_modern_tls(tls_handshake_report)


class TestCipher(unittest.TestCase):

    def test_pass(self):
        assert_cipher_safe(TlsHandshakeReport(
            host="x", cipher_suite="TLS_AES_256_GCM_SHA384",
        ))

    def test_fail(self):
        tls_handshake_report = TlsHandshakeReport(
            host="x", cipher_suite="TLS_RSA_WITH_RC4_128_SHA",
        )
        with self.assertRaises(TlsCipherAuditError):
            assert_cipher_safe(tls_handshake_report)

    def test_empty(self):
        tls_handshake_report = TlsHandshakeReport(host="x", cipher_suite="")
        with self.assertRaises(TlsCipherAuditError):
            assert_cipher_safe(tls_handshake_report)


class TestSubject(unittest.TestCase):

    def test_pass(self):
        assert_subject_matches(
            TlsHandshakeReport(host="x", cert_subject="CN=example.com/O=Example"),
            contains="example.com",
        )

    def test_fail(self):
        tls_handshake_report = TlsHandshakeReport(host="x", cert_subject="CN=other.com")
        with self.assertRaises(TlsCipherAuditError):
            assert_subject_matches(
                tls_handshake_report,
                contains="example.com",
            )

    def test_empty(self):
        tls_handshake_report = TlsHandshakeReport(host="x")
        with self.assertRaises(TlsCipherAuditError):
            assert_subject_matches(tls_handshake_report, contains="")


if __name__ == "__main__":
    unittest.main()
