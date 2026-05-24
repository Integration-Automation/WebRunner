"""Unit tests for je_web_runner.utils.pii_in_screenshot."""
import unittest

from je_web_runner.utils.pii_in_screenshot.scanner import (
    DEFAULT_RULES,
    PiiFinding,
    PiiInScreenshotError,
    ScanReport,
    assert_clean,
    scan_image,
    scan_screenshots,
    scan_text_only,
)


def _fake_backend(text):
    def _b(_source):
        return text
    return _b


class TestScanText(unittest.TestCase):

    def test_email_detected(self):
        findings = scan_text_only("Contact me at alice@example.com please")
        names = [f.rule for f in findings]
        self.assertIn("email", names)

    def test_credit_card_luhn_valid(self):
        # 4111-1111-1111-1111 is a well-known Luhn-valid test card
        findings = scan_text_only("Card: 4111 1111 1111 1111")
        names = [f.rule for f in findings]
        self.assertIn("credit_card", names)

    def test_credit_card_luhn_invalid_skipped(self):
        # 1234-5678-9012-3456 fails Luhn
        findings = scan_text_only("Bogus: 1234 5678 9012 3456")
        self.assertNotIn("credit_card", [f.rule for f in findings])

    def test_ssn_us(self):
        findings = scan_text_only("SSN: 123-45-6789")
        self.assertIn("ssn_us", [f.rule for f in findings])

    def test_tw_id(self):
        findings = scan_text_only("ID: A123456789")
        self.assertIn("tw_national_id", [f.rule for f in findings])

    def test_phone_e164(self):
        findings = scan_text_only("Tel: +1 415-555-1212")
        self.assertIn("phone_e164", [f.rule for f in findings])

    def test_iban(self):
        findings = scan_text_only("IBAN GB82WEST12345698765432")
        self.assertIn("iban", [f.rule for f in findings])

    def test_ipv4(self):
        findings = scan_text_only("server 192.168.1.50 down")
        self.assertIn("ipv4", [f.rule for f in findings])

    def test_dedup(self):
        text = "alice@x.com\nalice@x.com\nalice@x.com"
        findings = scan_text_only(text)
        emails = [f for f in findings if f.rule == "email"]
        self.assertEqual(len(emails), 1)

    def test_redaction_format(self):
        findings = scan_text_only("alice@example.com")
        self.assertTrue(findings[0].redacted_match.startswith("al"))
        self.assertIn("…", findings[0].redacted_match)

    def test_excerpt_marks_pii(self):
        findings = scan_text_only("hello alice@x.com world")
        self.assertIn("<<PII>>", findings[0].raw_excerpt)

    def test_non_string_rejected(self):
        with self.assertRaises(PiiInScreenshotError):
            scan_text_only(123)  # type: ignore[arg-type]  # NOSONAR S5655 — intentional bad-input test

    def test_clean_text(self):
        self.assertEqual(scan_text_only("no secrets here"), [])


class TestScanImage(unittest.TestCase):

    def test_uses_backend(self):
        findings = scan_image(b"", backend=_fake_backend("ssn 123-45-6789"))
        self.assertIn("ssn_us", [f.rule for f in findings])

    def test_ocr_error_wrapped(self):
        def boom(_):
            raise RuntimeError("bad image")
        with self.assertRaises(PiiInScreenshotError):
            scan_image(b"", backend=boom)


class TestScanScreenshots(unittest.TestCase):

    def test_scans_each_image(self):
        backends = [
            _fake_backend("alice@x.com"),
            _fake_backend("4111 1111 1111 1111"),
            _fake_backend("clean image"),
        ]
        report = ScanReport()
        for i, b in enumerate(backends):
            for f in scan_image(b"", backend=b, image_label=f"img_{i}"):
                report.findings.append(f)
                report.by_severity[f.severity] = report.by_severity.get(f.severity, 0) + 1
            report.scanned += 1
        self.assertEqual(report.scanned, 3)
        self.assertEqual(len(report.findings), 2)

    def test_rejects_empty_sources(self):
        with self.assertRaises(PiiInScreenshotError):
            scan_screenshots([])

    def test_scan_screenshots_aggregates(self):
        report = scan_screenshots(
            [b"a", b"b"],
            backend=_fake_backend("alice@x.com"),
        )
        self.assertEqual(report.scanned, 2)
        # Two images, same PII → finding labels differ → 2 records
        self.assertEqual(len(report.findings), 2)


class TestAssertClean(unittest.TestCase):

    def test_clean_passes(self):
        assert_clean(ScanReport())

    def test_dirty_raises(self):
        report = ScanReport(
            scanned=1,
            findings=[PiiFinding(
                rule="email", severity="medium", redacted_match="al…om",
                image="x",
            )],
        )
        with self.assertRaises(PiiInScreenshotError):
            assert_clean(report)

    def test_rejects_non_report(self):
        with self.assertRaises(PiiInScreenshotError):
            assert_clean("not a report")  # type: ignore[arg-type]


class TestDefaultRules(unittest.TestCase):

    def test_defaults_loaded(self):
        names = {r.name for r in DEFAULT_RULES}
        self.assertIn("email", names)
        self.assertIn("credit_card", names)
        self.assertIn("ssn_us", names)


if __name__ == "__main__":
    unittest.main()
