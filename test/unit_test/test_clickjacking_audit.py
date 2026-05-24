"""Unit tests for je_web_runner.utils.clickjacking_audit."""
import unittest

from je_web_runner.utils.clickjacking_audit.audit import (
    AuditReport,
    ClickjackingAuditError,
    HeaderPolicy,
    PROBE_STATUS_SCRIPT,
    Verdict,
    assert_protected,
    audit,
    build_probe_page,
    classify,
    parse_response_headers,
)


class TestParse(unittest.TestCase):

    def test_xfo_deny(self):
        p = parse_response_headers([("X-Frame-Options", "DENY")])
        self.assertEqual(p.x_frame_options, "DENY")

    def test_csp_frame_ancestors(self):
        p = parse_response_headers([
            ("Content-Security-Policy",
             "default-src 'self'; frame-ancestors 'none'; img-src *"),
        ])
        self.assertIn("'none'", p.csp_frame_ancestors or "")

    def test_csp_no_frame_ancestors(self):
        p = parse_response_headers([
            ("Content-Security-Policy", "default-src 'self'"),
        ])
        self.assertIsNone(p.csp_frame_ancestors)

    def test_ignores_non_strings(self):
        p = parse_response_headers([(None, "X"), ("X", None)])  # type: ignore[list-item]
        self.assertIsNone(p.x_frame_options)

    def test_case_insensitive(self):
        p = parse_response_headers([("x-frame-options", "deny")])
        self.assertEqual(p.normalized_xfo(), "DENY")


class TestClassify(unittest.TestCase):

    def test_csp_none_strict(self):
        self.assertEqual(
            classify(HeaderPolicy(csp_frame_ancestors="'none'")), Verdict.STRICT,
        )

    def test_csp_self_sameorigin(self):
        self.assertEqual(
            classify(HeaderPolicy(csp_frame_ancestors="'self'")), Verdict.SAMEORIGIN,
        )

    def test_csp_wildcard_allowed(self):
        self.assertEqual(
            classify(HeaderPolicy(csp_frame_ancestors="*")), Verdict.ALLOWED,
        )

    def test_csp_https_scheme_allowed(self):
        self.assertEqual(
            classify(HeaderPolicy(csp_frame_ancestors="https:")), Verdict.ALLOWED,
        )

    def test_csp_specific_origin_allowed(self):
        self.assertEqual(
            classify(HeaderPolicy(csp_frame_ancestors="https://trusted.com")),
            Verdict.ALLOWED,
        )

    def test_xfo_deny(self):
        self.assertEqual(
            classify(HeaderPolicy(x_frame_options="DENY")), Verdict.STRICT,
        )

    def test_xfo_sameorigin(self):
        self.assertEqual(
            classify(HeaderPolicy(x_frame_options="SAMEORIGIN")), Verdict.SAMEORIGIN,
        )

    def test_xfo_allow_from(self):
        self.assertEqual(
            classify(HeaderPolicy(x_frame_options="ALLOW-FROM https://x.com")),
            Verdict.ALLOWED,
        )

    def test_missing(self):
        self.assertEqual(classify(HeaderPolicy()), Verdict.MISSING)

    def test_csp_overrides_xfo(self):
        # CSP frame-ancestors is the modern source of truth.
        v = classify(HeaderPolicy(
            x_frame_options="SAMEORIGIN", csp_frame_ancestors="'none'",
        ))
        self.assertEqual(v, Verdict.STRICT)

    def test_rejects_non_policy(self):
        with self.assertRaises(ClickjackingAuditError):
            classify("not policy")  # type: ignore[arg-type]


class TestProbe(unittest.TestCase):

    def test_renders_target(self):
        html = build_probe_page("https://example.com/login")
        self.assertIn("https://example.com/login", html)
        self.assertIn("iframe", html)

    def test_bad_url(self):
        with self.assertRaises(ClickjackingAuditError):
            build_probe_page("")
        with self.assertRaises(ClickjackingAuditError):
            build_probe_page("ftp://x.com")

    def test_status_script_constant(self):
        self.assertIn("status", PROBE_STATUS_SCRIPT)


class TestAudit(unittest.TestCase):

    def test_strict_no_probe_passes(self):
        report = audit("https://x.com", [("X-Frame-Options", "DENY")])
        self.assertTrue(report.passed())

    def test_missing_fails(self):
        report = audit("https://x.com", [])
        self.assertFalse(report.passed())
        self.assertIn("no X-Frame-Options", " ".join(report.notes))

    def test_allowed_fails(self):
        report = audit("https://x.com", [
            ("Content-Security-Policy", "frame-ancestors *"),
        ])
        self.assertEqual(report.verdict, Verdict.ALLOWED)
        self.assertFalse(report.passed())

    def test_probe_overrides_when_embedded(self):
        report = audit("https://x.com",
                       [("X-Frame-Options", "DENY")],
                       probe_status="EMBEDDED")
        self.assertFalse(report.passed())

    def test_probe_blocked_passes(self):
        report = audit("https://x.com",
                       [("X-Frame-Options", "DENY")],
                       probe_status="BLOCKED")
        self.assertTrue(report.passed())

    def test_to_dict(self):
        report = audit("https://x.com", [("X-Frame-Options", "DENY")])
        data = report.to_dict()
        self.assertEqual(data["verdict"], "strict")
        self.assertTrue(data["passed"])


class TestAssertProtected(unittest.TestCase):

    def test_pass(self):
        assert_protected(audit("https://x.com", [("X-Frame-Options", "DENY")]))

    def test_fail(self):
        with self.assertRaises(ClickjackingAuditError):
            assert_protected(audit("https://x.com", []))

    def test_rejects_non_report(self):
        with self.assertRaises(ClickjackingAuditError):
            assert_protected("not a report")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
