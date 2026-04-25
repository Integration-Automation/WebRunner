import unittest
from unittest.mock import MagicMock, patch

from je_web_runner.utils.security_headers.headers_audit import (
    SecurityHeadersError,
    audit_headers,
    audit_url,
)


def _good_headers() -> dict:
    return {
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Content-Security-Policy": "default-src 'self'",
        "X-Frame-Options": "DENY",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "strict-origin",
        "Permissions-Policy": "camera=()",
    }


class TestAuditHeaders(unittest.TestCase):

    def test_clean_response_has_no_findings(self):
        self.assertEqual(audit_headers(_good_headers()), [])

    def test_missing_header_flagged(self):
        headers = _good_headers()
        del headers["Content-Security-Policy"]
        findings = audit_headers(headers)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["header"], "Content-Security-Policy")
        self.assertEqual(findings[0]["problem"], "missing")

    def test_hsts_without_max_age_flagged(self):
        headers = _good_headers()
        headers["Strict-Transport-Security"] = "includeSubDomains"
        findings = audit_headers(headers)
        self.assertEqual(len(findings), 1)
        self.assertIn("max-age", findings[0]["problem"])

    def test_x_frame_options_invalid_value(self):
        headers = _good_headers()
        headers["X-Frame-Options"] = "ALLOWALL"
        findings = audit_headers(headers)
        self.assertTrue(any(f["header"] == "X-Frame-Options" for f in findings))

    def test_x_content_type_options_must_be_nosniff(self):
        headers = _good_headers()
        headers["X-Content-Type-Options"] = "off"
        findings = audit_headers(headers)
        self.assertTrue(any(f["header"] == "X-Content-Type-Options" for f in findings))

    def test_lookup_is_case_insensitive(self):
        headers = {key.lower(): value for key, value in _good_headers().items()}
        self.assertEqual(audit_headers(headers), [])

    def test_custom_required_list(self):
        headers = {"X-Custom": "ok"}
        rules = [{"name": "X-Custom", "rule": "presence"}]
        self.assertEqual(audit_headers(headers, required=rules), [])


class TestAuditUrl(unittest.TestCase):

    def test_invalid_scheme_raises(self):
        with self.assertRaises(SecurityHeadersError):
            audit_url("ftp://example.com")

    def test_fetches_and_audits(self):
        response = MagicMock()
        response.headers = _good_headers()
        with patch("je_web_runner.utils.security_headers.headers_audit.requests.get",
                   return_value=response) as get_mock:
            self.assertEqual(audit_url("https://example.com"), [])
            get_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
