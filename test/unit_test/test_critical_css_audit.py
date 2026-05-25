"""Unit tests for je_web_runner.utils.critical_css_audit."""
import unittest

from je_web_runner.utils.critical_css_audit.audit import (
    CriticalCssAuditError,
    CssReport,
    analyse,
    assert_external_preloaded,
    assert_has_inline_critical,
    assert_inline_within_budget,
)


GOOD = """
<head>
  <style>.a{color:red}</style>
  <link rel="stylesheet" href="/main.css">
  <link rel="preload" href="/main.css" as="style">
</head>
"""

NO_INLINE = """
<head>
  <link rel="stylesheet" href="/main.css">
</head>
"""


class TestAnalyse(unittest.TestCase):

    def test_basic(self):
        r = analyse(GOOD)
        self.assertEqual(r.inline_blocks, 1)
        self.assertIn("/main.css", r.external_blocking)
        self.assertIn("/main.css", r.preloaded)

    def test_no_head(self):
        r = analyse("<style>x{}</style>")
        self.assertEqual(r.inline_blocks, 1)

    def test_print_skipped(self):
        r = analyse('<head><link rel="stylesheet" href="/p.css" media="print"></head>')
        self.assertEqual(r.external_blocking, [])

    def test_bad(self):
        with self.assertRaises(CriticalCssAuditError):
            analyse(123)


class TestInline(unittest.TestCase):

    def test_pass(self):
        assert_has_inline_critical(CssReport(inline_blocks=1))

    def test_fail(self):
        with self.assertRaises(CriticalCssAuditError):
            assert_has_inline_critical(CssReport())


class TestBudget(unittest.TestCase):

    def test_pass(self):
        assert_inline_within_budget(CssReport(inline_bytes=1024))

    def test_fail(self):
        with self.assertRaises(CriticalCssAuditError):
            assert_inline_within_budget(CssReport(inline_bytes=20_000))

    def test_bad_max(self):
        with self.assertRaises(CriticalCssAuditError):
            assert_inline_within_budget(CssReport(), max_bytes=0)


class TestPreloaded(unittest.TestCase):

    def test_pass(self):
        assert_external_preloaded(CssReport(
            external_blocking=["/a.css"], preloaded=["/a.css"],
        ))

    def test_fail(self):
        with self.assertRaises(CriticalCssAuditError):
            assert_external_preloaded(CssReport(
                external_blocking=["/a.css"], preloaded=[],
            ))


if __name__ == "__main__":
    unittest.main()
