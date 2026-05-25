"""Unit tests for je_web_runner.utils.viewport_audit."""
import unittest

from je_web_runner.utils.viewport_audit.audit import (
    HARVEST_SCRIPT,
    SafeAreaSnapshot,
    ViewportAuditError,
    ViewportMeta,
    assert_meta_present,
    assert_notch_aware,
    assert_responsive_width,
    assert_safe_area_padding,
    assert_user_scalable_allowed,
    parse_meta,
    parse_safe_area,
)


GOOD_META = ('<meta name="viewport" content="width=device-width, '
             'initial-scale=1, viewport-fit=cover">')
BAD_META = ('<meta name="viewport" content="width=320, user-scalable=no, '
            'maximum-scale=1">')


class TestParseMeta(unittest.TestCase):

    def test_good(self):
        meta = parse_meta(f"<html><head>{GOOD_META}</head></html>")
        self.assertEqual(meta.parsed["width"], "device-width")

    def test_missing(self):
        self.assertIsNone(parse_meta("<html></html>"))

    def test_bad_input(self):
        with self.assertRaises(ViewportAuditError):
            parse_meta(123)  # NOSONAR python:S5655 - deliberate bad input


class TestPresent(unittest.TestCase):

    def test_pass(self):
        assert_meta_present(ViewportMeta())

    def test_fail(self):
        with self.assertRaises(ViewportAuditError):
            assert_meta_present(None)


class TestWidth(unittest.TestCase):

    def test_pass(self):
        assert_responsive_width(parse_meta(f"<head>{GOOD_META}</head>"))

    def test_fail(self):
        with self.assertRaises(ViewportAuditError):
            assert_responsive_width(parse_meta(f"<head>{BAD_META}</head>"))


class TestScalable(unittest.TestCase):

    def test_pass(self):
        assert_user_scalable_allowed(parse_meta(f"<head>{GOOD_META}</head>"))

    def test_fail_no(self):
        with self.assertRaises(ViewportAuditError):
            assert_user_scalable_allowed(parse_meta(f"<head>{BAD_META}</head>"))

    def test_fail_low_max(self):
        html = '<meta name="viewport" content="width=device-width, maximum-scale=1">'
        with self.assertRaises(ViewportAuditError):
            assert_user_scalable_allowed(parse_meta(f"<head>{html}</head>"))

    def test_bad_max(self):
        html = '<meta name="viewport" content="width=device-width, maximum-scale=abc">'
        with self.assertRaises(ViewportAuditError):
            assert_user_scalable_allowed(parse_meta(f"<head>{html}</head>"))


class TestNotch(unittest.TestCase):

    def test_pass(self):
        assert_notch_aware(parse_meta(f"<head>{GOOD_META}</head>"))

    def test_fail(self):
        html = '<meta name="viewport" content="width=device-width">'
        with self.assertRaises(ViewportAuditError):
            assert_notch_aware(parse_meta(f"<head>{html}</head>"))


class TestSafeArea(unittest.TestCase):

    def test_script(self):
        self.assertIn("getComputedStyle", HARVEST_SCRIPT)

    def test_parse(self):
        snap = parse_safe_area({"padding_top": "44px"})
        self.assertEqual(snap.padding_top, "44px")

    def test_parse_bad(self):
        with self.assertRaises(ViewportAuditError):
            parse_safe_area("nope")

    def test_assert_pass(self):
        assert_safe_area_padding(SafeAreaSnapshot(padding_top="44px"))

    def test_assert_fail(self):
        with self.assertRaises(ViewportAuditError):
            assert_safe_area_padding(SafeAreaSnapshot())


if __name__ == "__main__":
    unittest.main()
