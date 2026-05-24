"""Unit tests for je_web_runner.utils.coop_coep_audit."""
import json
import unittest

from je_web_runner.utils.coop_coep_audit.audit import (
    CoepValue,
    CoopCoepAuditError,
    CoopValue,
    assert_isolated,
    audit_isolation,
    parse_page_headers,
    scan_har_resources,
)


def _har_entry(url, headers=None):
    return {
        "request": {"url": url},
        "response": {
            "headers": [
                {"name": k, "value": v} for k, v in (headers or {}).items()
            ],
        },
    }


def _har(*entries):
    return {"log": {"entries": list(entries)}}


class TestParsePageHeaders(unittest.TestCase):

    def test_full_isolation(self):
        p = parse_page_headers([
            ("Cross-Origin-Opener-Policy", "same-origin"),
            ("Cross-Origin-Embedder-Policy", "require-corp"),
        ])
        self.assertTrue(p.isolated())

    def test_partial_isolation(self):
        p = parse_page_headers([
            ("Cross-Origin-Opener-Policy", "same-origin"),
        ])
        self.assertFalse(p.isolated())

    def test_credentialless_isolated(self):
        p = parse_page_headers([
            ("Cross-Origin-Opener-Policy", "same-origin"),
            ("Cross-Origin-Embedder-Policy", "credentialless"),
        ])
        self.assertTrue(p.isolated())

    def test_unknown_falls_to_unsafe_none(self):
        p = parse_page_headers([
            ("Cross-Origin-Opener-Policy", "weird"),
        ])
        self.assertEqual(p.coop, CoopValue.UNSAFE_NONE)

    def test_ignores_non_strings(self):
        p = parse_page_headers([(None, "x"), ("x", None)])  # type: ignore[list-item]
        self.assertEqual(p.coop, CoopValue.UNSAFE_NONE)

    def test_default_policy(self):
        p = parse_page_headers([])
        self.assertFalse(p.isolated())


class TestScanResources(unittest.TestCase):

    def test_unsafe_none_skips(self):
        findings = scan_har_resources(
            _har(_har_entry("https://other.com/x.js")),
            page_url="https://main.com/",
            coep=CoepValue.UNSAFE_NONE,
        )
        self.assertEqual(findings, [])

    def test_same_origin_skipped(self):
        findings = scan_har_resources(
            _har(_har_entry("https://main.com/x.js")),
            page_url="https://main.com/",
            coep=CoepValue.REQUIRE_CORP,
        )
        self.assertEqual(findings, [])

    def test_require_corp_with_corp_cross_origin_ok(self):
        findings = scan_har_resources(
            _har(_har_entry("https://cdn/x.js", {
                "Cross-Origin-Resource-Policy": "cross-origin",
            })),
            page_url="https://main.com/",
            coep=CoepValue.REQUIRE_CORP,
        )
        self.assertEqual(findings, [])

    def test_require_corp_with_cors_ok(self):
        findings = scan_har_resources(
            _har(_har_entry("https://cdn/x.js", {
                "Access-Control-Allow-Origin": "*",
            })),
            page_url="https://main.com/",
            coep=CoepValue.REQUIRE_CORP,
        )
        self.assertEqual(findings, [])

    def test_require_corp_missing_flagged(self):
        findings = scan_har_resources(
            _har(_har_entry("https://cdn/x.js", {})),
            page_url="https://main.com/",
            coep=CoepValue.REQUIRE_CORP,
        )
        self.assertEqual(len(findings), 1)
        self.assertIn("require-corp", findings[0].reason)

    def test_cors_null_not_enough(self):
        findings = scan_har_resources(
            _har(_har_entry("https://cdn/x.js", {
                "Access-Control-Allow-Origin": "null",
            })),
            page_url="https://main.com/",
            coep=CoepValue.REQUIRE_CORP,
        )
        self.assertEqual(len(findings), 1)

    def test_credentialless(self):
        findings = scan_har_resources(
            _har(_har_entry("https://cdn/x.js", {})),
            page_url="https://main.com/",
            coep=CoepValue.CREDENTIALLESS,
        )
        self.assertEqual(len(findings), 1)
        findings = scan_har_resources(
            _har(_har_entry("https://cdn/x.js", {
                "Cross-Origin-Resource-Policy": "cross-origin",
            })),
            page_url="https://main.com/",
            coep=CoepValue.CREDENTIALLESS,
        )
        self.assertEqual(findings, [])

    def test_har_str(self):
        findings = scan_har_resources(
            json.dumps(_har(_har_entry("https://main.com/x.js"))),
            page_url="https://main.com/",
            coep=CoepValue.REQUIRE_CORP,
        )
        self.assertEqual(findings, [])

    def test_bad_har(self):
        with self.assertRaises(CoopCoepAuditError):
            scan_har_resources(
                "not json", page_url="https://main.com/",
                coep=CoepValue.REQUIRE_CORP,
            )

    def test_bad_har_type(self):
        with self.assertRaises(CoopCoepAuditError):
            scan_har_resources(
                123, page_url="https://main.com/",  # type: ignore[arg-type]
                coep=CoepValue.REQUIRE_CORP,
            )

    def test_bad_page_url(self):
        with self.assertRaises(CoopCoepAuditError):
            scan_har_resources(_har(), page_url="", coep=CoepValue.REQUIRE_CORP)


class TestAuditIsolation(unittest.TestCase):

    def test_fully_isolated(self):
        report = audit_isolation(
            "https://main.com/",
            [("Cross-Origin-Opener-Policy", "same-origin"),
             ("Cross-Origin-Embedder-Policy", "require-corp")],
            har=_har(),
        )
        self.assertTrue(report.passed())

    def test_no_coop(self):
        report = audit_isolation(
            "https://main.com/",
            [("Cross-Origin-Embedder-Policy", "require-corp")],
        )
        self.assertFalse(report.passed())
        self.assertTrue(any("COOP" in n for n in report.notes))

    def test_resource_violation(self):
        report = audit_isolation(
            "https://main.com/",
            [("Cross-Origin-Opener-Policy", "same-origin"),
             ("Cross-Origin-Embedder-Policy", "require-corp")],
            har=_har(_har_entry("https://cdn/x.js", {})),
        )
        self.assertFalse(report.passed())
        self.assertEqual(len(report.resource_findings), 1)

    def test_to_dict(self):
        report = audit_isolation(
            "https://main.com/",
            [("Cross-Origin-Opener-Policy", "same-origin"),
             ("Cross-Origin-Embedder-Policy", "require-corp")],
        )
        d = report.to_dict()
        self.assertTrue(d["passed"])
        self.assertEqual(d["policy"]["coop"], "same-origin")

    def test_bad_page_url(self):
        with self.assertRaises(CoopCoepAuditError):
            audit_isolation("", [])


class TestAssertIsolated(unittest.TestCase):

    def test_pass(self):
        report = audit_isolation(
            "https://main.com/",
            [("Cross-Origin-Opener-Policy", "same-origin"),
             ("Cross-Origin-Embedder-Policy", "require-corp")],
        )
        assert_isolated(report)

    def test_fail_not_isolated(self):
        with self.assertRaises(CoopCoepAuditError):
            assert_isolated(audit_isolation("https://main.com/", []))

    def test_fail_resource(self):
        report = audit_isolation(
            "https://main.com/",
            [("Cross-Origin-Opener-Policy", "same-origin"),
             ("Cross-Origin-Embedder-Policy", "require-corp")],
            har=_har(_har_entry("https://cdn/x.js", {})),
        )
        with self.assertRaises(CoopCoepAuditError):
            assert_isolated(report)

    def test_rejects_non_report(self):
        with self.assertRaises(CoopCoepAuditError):
            assert_isolated("nope")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
