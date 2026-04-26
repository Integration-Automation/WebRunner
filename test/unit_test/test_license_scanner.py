import unittest

from je_web_runner.utils.license_scanner import (
    LicenseScannerError,
    assert_allowed_licenses,
    scan_text,
)
from je_web_runner.utils.license_scanner.scanner import summarise


class TestScanText(unittest.TestCase):

    def test_finds_spdx_identifier(self):
        text = "/*! SPDX-License-Identifier: MIT */"
        findings = scan_text(text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].license_id, "MIT")

    def test_finds_keyword_license(self):
        text = "Apache License, Version 2.0\nbla"
        findings = scan_text(text)
        ids = [f.license_id for f in findings]
        self.assertIn("Apache-2.0", ids)

    def test_detects_agpl(self):
        text = "GNU AFFERO GENERAL PUBLIC LICENSE Version 3"
        findings = scan_text(text)
        self.assertIn("AGPL-3.0", [f.license_id for f in findings])

    def test_summarise(self):
        text = (
            "SPDX-License-Identifier: MIT\n"
            "Apache License, Version 2.0\n"
        )
        counts = summarise(scan_text(text))
        self.assertEqual(counts["MIT"], 1)
        self.assertEqual(counts["Apache-2.0"], 1)

    def test_non_string_raises(self):
        with self.assertRaises(LicenseScannerError):
            scan_text(123)  # type: ignore[arg-type]


class TestAssertAllowedLicenses(unittest.TestCase):

    def test_passes_when_all_allowed(self):
        text = "SPDX-License-Identifier: MIT"
        assert_allowed_licenses(scan_text(text), allow=["MIT"])

    def test_fails_when_disallowed_present(self):
        text = "GNU AFFERO GENERAL PUBLIC LICENSE Version 3"
        with self.assertRaises(LicenseScannerError):
            assert_allowed_licenses(scan_text(text), allow=["MIT"])

    def test_deny_overrides_allow(self):
        text = "SPDX-License-Identifier: GPL-3.0"
        with self.assertRaises(LicenseScannerError):
            assert_allowed_licenses(
                scan_text(text), allow=["GPL-3.0", "MIT"], deny=["GPL-3.0"],
            )


if __name__ == "__main__":
    unittest.main()
