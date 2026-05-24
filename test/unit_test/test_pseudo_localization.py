"""Unit tests for je_web_runner.utils.pseudo_localization."""
import unittest

from je_web_runner.utils.pseudo_localization.pseudo import (
    PseudoAuditReport,
    PseudoConfig,
    PseudoLocalizationError,
    pseudo_localize,
    pseudo_localize_dict,
    scan_for_hardcoded,
)


class TestPseudoLocalize(unittest.TestCase):

    def test_default_wraps_and_accents(self):
        out = pseudo_localize("Hello")
        self.assertTrue(out.startswith("⟦"))
        self.assertTrue(out.endswith("⟧"))
        self.assertIn("é", out.lower())
        self.assertIn("─", out)

    def test_disable_bracket(self):
        out = pseudo_localize("hi", PseudoConfig(bracket=False))
        self.assertFalse(out.startswith("⟦"))

    def test_disable_accent(self):
        out = pseudo_localize("hello", PseudoConfig(accent=False, bracket=False))
        self.assertIn("hello", out)

    def test_expansion_grows_string(self):
        cfg = PseudoConfig(accent=False, expansion_ratio=1.0, bracket=False)
        out = pseudo_localize("hi", cfg)
        # 1.0 ratio: original 2 chars + ~2 padding + spaces
        self.assertGreater(len(out), 4)

    def test_no_expansion(self):
        cfg = PseudoConfig(accent=False, expansion_ratio=0.0, bracket=False)
        self.assertEqual(pseudo_localize("hi", cfg), "hi")

    def test_preserves_braced_placeholder(self):
        out = pseudo_localize("Hello {name}", PseudoConfig(
            expansion_ratio=0, bracket=False,
        ))
        self.assertIn("{name}", out)

    def test_preserves_printf_placeholder(self):
        out = pseudo_localize("Got %d items", PseudoConfig(
            expansion_ratio=0, bracket=False,
        ))
        self.assertIn("%d", out)

    def test_preserves_html_tag(self):
        out = pseudo_localize("<b>bold</b>", PseudoConfig(
            expansion_ratio=0, bracket=False,
        ))
        self.assertIn("<b>", out)
        self.assertIn("</b>", out)

    def test_empty_string_unchanged(self):
        self.assertEqual(pseudo_localize(""), "")

    def test_non_string_rejected(self):
        with self.assertRaises(PseudoLocalizationError):
            pseudo_localize(123)  # type: ignore[arg-type]  # NOSONAR S5655 — intentional bad-input test

    def test_negative_expansion_rejected(self):
        with self.assertRaises(PseudoLocalizationError):
            PseudoConfig(expansion_ratio=-1)


class TestPseudoLocalizeDict(unittest.TestCase):

    def test_translates_all_values(self):
        out = pseudo_localize_dict({"login": "Sign in", "logout": "Sign out"})
        self.assertEqual(set(out.keys()), {"login", "logout"})
        for value in out.values():
            self.assertTrue(value.startswith("⟦"))

    def test_rejects_non_mapping(self):
        with self.assertRaises(PseudoLocalizationError):
            pseudo_localize_dict([("a", "b")])  # type: ignore[arg-type]  # NOSONAR S5655 — intentional bad-input test

    def test_rejects_non_string_value(self):
        with self.assertRaises(PseudoLocalizationError):
            pseudo_localize_dict({"x": 123})  # type: ignore[dict-item]


class TestScanForHardcoded(unittest.TestCase):

    def test_finds_hardcoded(self):
        catalogue = {"submit": "Submit", "cancel": "Cancel"}
        # Submit appears verbatim → hardcoded leak
        rendered = "⟦Šubmît⟧ Submit ⟦Çančél⟧"
        report = scan_for_hardcoded(rendered, catalogue=catalogue)
        self.assertEqual(len(report.hits), 1)
        self.assertEqual(report.hits[0].string, "Submit")
        self.assertEqual(report.hits[0].occurrences, 1)
        self.assertFalse(report.passed())

    def test_clean(self):
        report = scan_for_hardcoded(
            "⟦Šubmît⟧ ⟦Çančél⟧",
            catalogue={"submit": "Submit", "cancel": "Cancel"},
        )
        self.assertTrue(report.passed())

    def test_min_length_filter(self):
        report = scan_for_hardcoded(
            "ok ok ok",
            catalogue={"ok": "ok"},
            min_length=3,
        )
        # 'ok' is too short → ignored
        self.assertTrue(report.passed())

    def test_skips_non_ascii_only_catalogue(self):
        # Catalogue value with no ASCII letters can't be detected as "hard-coded"
        report = scan_for_hardcoded(
            "你好 你好",
            catalogue={"hello": "你好"},
        )
        self.assertTrue(report.passed())

    def test_counts_multiple_occurrences(self):
        report = scan_for_hardcoded(
            "Submit Submit Submit",
            catalogue={"submit": "Submit"},
        )
        self.assertEqual(report.hits[0].occurrences, 3)

    def test_bad_inputs(self):
        with self.assertRaises(PseudoLocalizationError):
            scan_for_hardcoded(123, catalogue={})  # type: ignore[arg-type]  # NOSONAR S5655 — intentional bad-input test
        with self.assertRaises(PseudoLocalizationError):
            scan_for_hardcoded("x", catalogue={}, min_length=0)


class TestReport(unittest.TestCase):

    def test_default_passed(self):
        self.assertTrue(PseudoAuditReport().passed())


if __name__ == "__main__":
    unittest.main()
