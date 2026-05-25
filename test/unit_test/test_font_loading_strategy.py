"""Unit tests for je_web_runner.utils.font_loading_strategy."""
import unittest

from je_web_runner.utils.font_loading_strategy.strategy import (
    Display,
    FontFace,
    FontLoadingStrategyError,
    assert_display_strategy,
    assert_no_missing_display,
    assert_size_adjust_for_fallback,
    parse_font_faces,
)


CSS = """
@font-face {
  font-family: 'Inter';
  src: url('/fonts/inter.woff2') format('woff2');
  font-display: swap;
  font-weight: 400;
}
@font-face {
  font-family: 'Inter Fallback';
  src: local('Arial');
  size-adjust: 107%;
}
@font-face {
  font-family: 'BadFont';
  src: url('/fonts/bad.woff2');
}
"""


class TestParse(unittest.TestCase):

    def test_basic(self):
        faces = parse_font_faces(CSS)
        names = {f.family for f in faces}
        self.assertEqual(names, {"Inter", "Inter Fallback", "BadFont"})

    def test_unknown_display_becomes_missing(self):
        css = "@font-face { font-family: x; font-display: weird; }"
        faces = parse_font_faces(css)
        self.assertEqual(faces[0].display, Display.MISSING)

    def test_skip_no_family(self):
        faces = parse_font_faces("@font-face { src: x; }")
        self.assertEqual(faces, [])

    def test_bad(self):
        with self.assertRaises(FontLoadingStrategyError):
            parse_font_faces(123)


class TestMissing(unittest.TestCase):

    def test_pass(self):
        assert_no_missing_display([FontFace(family="x", display=Display.SWAP)])

    def test_fail(self):
        with self.assertRaises(FontLoadingStrategyError):
            assert_no_missing_display(parse_font_faces(CSS))


class TestStrategy(unittest.TestCase):

    def test_pass(self):
        assert_display_strategy(
            [FontFace(family="x", display=Display.SWAP)],
            strategy=Display.SWAP,
        )

    def test_fail(self):
        with self.assertRaises(FontLoadingStrategyError):
            assert_display_strategy(
                [FontFace(family="x", display=Display.BLOCK)],
                strategy=Display.SWAP,
            )

    def test_auto_rejected(self):
        with self.assertRaises(FontLoadingStrategyError):
            assert_display_strategy([], strategy=Display.AUTO)


class TestSizeAdjust(unittest.TestCase):

    def test_pass(self):
        faces = parse_font_faces(CSS)
        assert_size_adjust_for_fallback("Inter Fallback", faces)

    def test_fail_no_size_adjust(self):
        faces = [FontFace(family="x", display=Display.SWAP)]
        with self.assertRaises(FontLoadingStrategyError):
            assert_size_adjust_for_fallback("x", faces)

    def test_missing_family(self):
        with self.assertRaises(FontLoadingStrategyError):
            assert_size_adjust_for_fallback("Missing", [])


if __name__ == "__main__":
    unittest.main()
