import unittest

from je_web_runner.utils.pii_scanner import (
    PiiScannerError,
    assert_no_pii,
    scan_text,
)
from je_web_runner.utils.pii_scanner.scanner import redact_text, summarise


class TestScanText(unittest.TestCase):

    def test_email_detected(self):
        findings = scan_text("contact alice@example.com today")
        self.assertEqual([f.category for f in findings], ["email"])

    def test_phone_e164(self):
        findings = scan_text("call +14155552671 anytime")
        self.assertIn("phone_e164", [f.category for f in findings])

    def test_credit_card_with_luhn(self):
        # Visa test number that passes Luhn
        findings = scan_text("card 4111 1111 1111 1111 charged")
        self.assertIn("credit_card", [f.category for f in findings])

    def test_credit_card_invalid_luhn_skipped(self):
        findings = scan_text("not-a-card 4111 1111 1111 1112")
        self.assertNotIn("credit_card", [f.category for f in findings])

    def test_ssn(self):
        findings = scan_text("SSN 123-45-6789 on file")
        self.assertIn("ssn_us", [f.category for f in findings])

    def test_taiwan_id_valid_passes_checksum(self):
        # Sample valid ROC ID
        findings = scan_text("ID: A123456789")
        self.assertIn("taiwan_id", [f.category for f in findings])

    def test_taiwan_id_invalid_filtered(self):
        findings = scan_text("ID: A111111111")
        self.assertNotIn("taiwan_id", [f.category for f in findings])

    def test_ipv4(self):
        findings = scan_text("origin 192.168.1.1 last week")
        self.assertIn("ipv4", [f.category for f in findings])

    def test_categories_filter(self):
        findings = scan_text(
            "alice@example.com 192.168.0.1",
            categories=["email"],
        )
        self.assertEqual([f.category for f in findings], ["email"])

    def test_redacted_preview(self):
        findings = scan_text("alice@example.com")
        self.assertNotIn("alice@example.com", findings[0].redacted)
        self.assertTrue(findings[0].redacted.startswith("al"))

    def test_non_string_raises(self):
        with self.assertRaises(PiiScannerError):
            scan_text(123)  # type: ignore[arg-type]


class TestAssertAndSummarise(unittest.TestCase):

    def test_assert_no_pii_passes_clean(self):
        assert_no_pii("nothing sensitive here")

    def test_assert_no_pii_raises(self):
        with self.assertRaises(PiiScannerError):
            assert_no_pii("alice@example.com")

    def test_allow_categories_skip(self):
        assert_no_pii("alice@example.com", allow_categories=["email"])

    def test_summarise(self):
        counts = summarise(scan_text(
            "alice@example.com bob@example.com 192.168.1.1"
        ))
        self.assertEqual(counts["email"], 2)
        self.assertEqual(counts["ipv4"], 1)


class TestRedactText(unittest.TestCase):

    def test_replaces_matches(self):
        # NOSONAR S1313 — RFC1918 fixture, not a real environment address
        out = redact_text("from alice@example.com on 192.168.0.1")
        self.assertNotIn("alice@example.com", out)
        self.assertNotIn("192.168.0.1", out)
        self.assertIn("[REDACTED]", out)

    def test_clean_text_unchanged(self):
        self.assertEqual(redact_text("nothing here"), "nothing here")


if __name__ == "__main__":
    unittest.main()
