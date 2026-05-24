"""Unit tests for je_web_runner.utils.ocr_assert."""
import unittest

from je_web_runner.utils.ocr_assert.ocr import (
    OcrAssertError,
    OcrMatchResult,
    assert_text_any,
    assert_text_contains,
    assert_text_fuzzy,
    extract_text,
    fuzzy_ratio,
    normalise_text,
)


def _fake_backend(text):
    def _b(_source):
        return text
    return _b


class TestNormalisation(unittest.TestCase):

    def test_collapses_whitespace(self):
        self.assertEqual(normalise_text("hello   world\n\n"), "hello world")

    def test_lowercases_by_default(self):
        self.assertEqual(normalise_text("Hello"), "hello")

    def test_keeps_case_when_disabled(self):
        self.assertEqual(normalise_text("Hello", lowercase=False), "Hello")

    def test_strips_accents(self):
        self.assertEqual(normalise_text("café"), "cafe")

    def test_rejects_non_string(self):
        with self.assertRaises(OcrAssertError):
            normalise_text(123)  # type: ignore[arg-type]  # NOSONAR S5655 — intentional bad-input test

    def test_fuzzy_ratio_identical(self):
        self.assertEqual(fuzzy_ratio("hello", "hello"), 1.0)

    def test_fuzzy_ratio_partial(self):
        ratio = fuzzy_ratio("hello world", "helo world")
        self.assertGreater(ratio, 0.8)
        self.assertLess(ratio, 1.0)


class TestExtractText(unittest.TestCase):

    def test_uses_custom_backend(self):
        text = extract_text(b"", backend=_fake_backend("OCR OK"))
        self.assertEqual(text, "OCR OK")

    def test_rejects_non_string_backend_output(self):
        with self.assertRaises(OcrAssertError):
            extract_text(b"", backend=lambda _: 123)


class TestAssertContains(unittest.TestCase):

    def test_match(self):
        result = assert_text_contains(
            b"", "world", backend=_fake_backend("Hello, World!"),
        )
        self.assertTrue(result.matched)
        self.assertEqual(result.score, 1.0)

    def test_miss(self):
        result = assert_text_contains(
            b"", "missing", backend=_fake_backend("Hello, World!"),
        )
        self.assertFalse(result.matched)
        with self.assertRaises(OcrAssertError):
            result.raise_if_failed()

    def test_case_sensitive_miss(self):
        result = assert_text_contains(
            b"", "WORLD",
            backend=_fake_backend("hello world"),
            case_sensitive=True,
        )
        self.assertFalse(result.matched)

    def test_rejects_empty_needle(self):
        with self.assertRaises(OcrAssertError):
            assert_text_contains(b"", "", backend=_fake_backend("x"))


class TestAssertFuzzy(unittest.TestCase):

    def test_close_match(self):
        result = assert_text_fuzzy(
            b"", "Quarterly Revenue",
            min_ratio=0.7,
            backend=_fake_backend("Quartely Revnue"),
        )
        self.assertTrue(result.matched)
        self.assertGreater(result.score, 0.7)

    def test_far_off_fails(self):
        result = assert_text_fuzzy(
            b"", "Quarterly Revenue",
            min_ratio=0.9,
            backend=_fake_backend("totally different text here"),
        )
        self.assertFalse(result.matched)

    def test_rejects_bad_ratio(self):
        with self.assertRaises(OcrAssertError):
            assert_text_fuzzy(b"", "x", min_ratio=0.0, backend=_fake_backend("x"))
        with self.assertRaises(OcrAssertError):
            assert_text_fuzzy(b"", "x", min_ratio=1.5, backend=_fake_backend("x"))


class TestAssertAny(unittest.TestCase):

    def test_finds_first_match(self):
        result = assert_text_any(
            b"", ["foo", "bar", "baz"],
            backend=_fake_backend("There is a bar here"),
        )
        self.assertTrue(result.matched)
        self.assertEqual(result.needle, "bar")

    def test_no_match(self):
        result = assert_text_any(
            b"", ["alpha", "beta"],
            backend=_fake_backend("nothing relevant"),
        )
        self.assertFalse(result.matched)

    def test_rejects_empty(self):
        with self.assertRaises(OcrAssertError):
            assert_text_any(b"", [], backend=_fake_backend("x"))


class TestOcrMatchResult(unittest.TestCase):

    def test_raise_if_failed_noop_when_matched(self):
        OcrMatchResult(matched=True, mode="x", needle="n", haystack="h").raise_if_failed()


if __name__ == "__main__":
    unittest.main()
