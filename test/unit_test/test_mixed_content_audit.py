"""Unit tests for je_web_runner.utils.mixed_content_audit."""
import json
import unittest

from je_web_runner.utils.mixed_content_audit.audit import (
    MixedContentAuditError,
    MixedFinding,
    Severity,
    assert_clean,
    assert_no_active,
    scan_console_errors,
    scan_har,
    summary,
)


def _har_entry(url, resource_type="script"):
    return {
        "_resourceType": resource_type,
        "request": {"url": url},
        "response": {"content": {}},
    }


def _har(*entries):
    return {"log": {"entries": list(entries)}}


class TestScanHar(unittest.TestCase):

    def test_no_findings_for_clean_https(self):
        findings = scan_har(_har(_har_entry("https://x.com/a.js")),
                            page_url="https://x.com")
        self.assertEqual(findings, [])

    def test_active_finding(self):
        findings = scan_har(
            _har(_har_entry("http://x.com/bad.js", "script")),  # noqa: S5332
            page_url="https://x.com",
        )
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, Severity.ACTIVE)

    def test_passive_finding(self):
        findings = scan_har(
            _har(_har_entry("http://x.com/img.png", "image")),  # noqa: S5332
            page_url="https://x.com",
        )
        self.assertEqual(findings[0].severity, Severity.PASSIVE)

    def test_upgrade_for_hsts_domain(self):
        findings = scan_har(
            _har(_har_entry("http://fonts.googleapis.com/css", "stylesheet")),  # noqa: S5332
            page_url="https://x.com",
        )
        self.assertEqual(findings[0].severity, Severity.UPGRADE)

    def test_unknown_resource_type_active(self):
        findings = scan_har(
            _har(_har_entry("http://x.com/a", "weird")),  # noqa: S5332
            page_url="https://x.com",
        )
        self.assertEqual(findings[0].severity, Severity.ACTIVE)

    def test_http_page_no_risk(self):
        findings = scan_har(
            _har(_har_entry("http://x.com/a.js")),  # noqa: S5332
            page_url="http://x.com",  # noqa: S5332
        )
        self.assertEqual(findings, [])

    def test_str_har(self):
        findings = scan_har(
            json.dumps(_har(_har_entry("http://x.com/a.js"))),  # noqa: S5332
            page_url="https://x.com",
        )
        self.assertEqual(len(findings), 1)

    def test_bad_har(self):
        with self.assertRaises(MixedContentAuditError):
            scan_har("not json")

    def test_bad_har_type(self):
        with self.assertRaises(MixedContentAuditError):
            scan_har(123)  # type: ignore[arg-type]

    def test_bad_har_root(self):
        with self.assertRaises(MixedContentAuditError):
            scan_har("[]")

    def test_page_url_inferred_from_har_pages(self):
        har = {
            "log": {
                "pages": [{"title": "https://example.com/"}],
                "entries": [_har_entry("http://example.com/img.png", "image")],  # noqa: S5332
            }
        }
        findings = scan_har(har)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].source_url, "https://example.com/")

    def test_no_page_url_assumes_https(self):
        # When page_url is empty AND no pages array, still scans
        findings = scan_har(_har(_har_entry("http://x.com/a.png", "image")))  # noqa: S5332
        self.assertEqual(len(findings), 1)


class TestScanConsole(unittest.TestCase):

    def test_active_message(self):
        msgs = ['Mixed Content: The page at https://x.com requested an insecure script http://x.com/bad.js. This request has been blocked.']
        findings = scan_console_errors(msgs, page_url="https://x.com")
        self.assertEqual(findings[0].severity, Severity.ACTIVE)
        self.assertIn("bad.js", findings[0].url)

    def test_passive_message(self):
        msgs = ['Mixed Content: passive image http://x.com/img.png was loaded over HTTP.']
        findings = scan_console_errors(msgs)
        self.assertEqual(findings[0].severity, Severity.PASSIVE)

    def test_ignores_unrelated(self):
        msgs = ["TypeError: foo is not a function", "Some other log"]
        self.assertEqual(scan_console_errors(msgs), [])

    def test_ignores_non_string(self):
        self.assertEqual(scan_console_errors([None, 1]), [])  # type: ignore[list-item]

    def test_skips_https_url_in_message(self):
        msgs = ["Mixed Content message containing https://x.com/foo"]
        # https URL in message → don't classify as finding
        self.assertEqual(scan_console_errors(msgs), [])


class TestAssertions(unittest.TestCase):

    def test_assert_no_active_pass(self):
        assert_no_active([
            MixedFinding(url="http://x", resource_type="image",  # noqa: S5332
                         severity=Severity.PASSIVE),
        ])

    def test_assert_no_active_fail(self):
        with self.assertRaises(MixedContentAuditError):
            assert_no_active([
                MixedFinding(url="http://x", resource_type="script",  # noqa: S5332
                             severity=Severity.ACTIVE),
            ])

    def test_assert_clean_pass(self):
        assert_clean([])

    def test_assert_clean_fail(self):
        with self.assertRaises(MixedContentAuditError):
            assert_clean([
                MixedFinding(url="http://x", resource_type="image",  # noqa: S5332
                             severity=Severity.PASSIVE),
            ])


class TestSummary(unittest.TestCase):

    def test_counts_severities(self):
        s = summary([
            MixedFinding(url="a", resource_type="x", severity=Severity.ACTIVE),
            MixedFinding(url="b", resource_type="x", severity=Severity.ACTIVE),
            MixedFinding(url="c", resource_type="x", severity=Severity.PASSIVE),
        ])
        self.assertEqual(s, {"active": 2, "passive": 1})

    def test_empty(self):
        self.assertEqual(summary([]), {})


if __name__ == "__main__":
    unittest.main()
