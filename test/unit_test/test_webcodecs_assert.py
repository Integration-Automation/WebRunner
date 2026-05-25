"""Unit tests for je_web_runner.utils.webcodecs_assert."""
import unittest

from je_web_runner.utils.webcodecs_assert.assertions import (
    ChunkType,
    HARVEST_SCRIPT,
    WebcodecsAssertError,
    assert_codec,
    assert_framerate_at_least,
    assert_keyframe_interval,
    assert_resolution,
    estimate_framerate,
    parse_chunks,
)


def _chunk(type_="delta", **kw):
    base = {"type": type_, "timestamp": 0, "duration": 33_000,
            "byteLength": 0, "codec": "avc1.42E01E",
            "width": 1280, "height": 720}
    base.update(kw)
    return base


class TestParse(unittest.TestCase):

    def test_basic(self):
        chunks = parse_chunks([_chunk("key"), _chunk("delta")])
        self.assertEqual(chunks[0].type, ChunkType.KEY)

    def test_script(self):
        self.assertIn("__wr_codec__", HARVEST_SCRIPT)

    def test_unknown_type(self):
        with self.assertRaises(WebcodecsAssertError):
            parse_chunks([{"type": "weird"}])

    def test_bad_payload(self):
        with self.assertRaises(WebcodecsAssertError):
            parse_chunks("nope")

    def test_skip_non_dict(self):
        self.assertEqual(parse_chunks(["x"]), [])


class TestCodec(unittest.TestCase):

    def test_pass(self):
        assert_codec(parse_chunks([_chunk()]), "avc1.42E01E")

    def test_fail(self):
        with self.assertRaises(WebcodecsAssertError):
            assert_codec(parse_chunks([_chunk(codec="vp9")]), "avc1.42E01E")

    def test_empty(self):
        with self.assertRaises(WebcodecsAssertError):
            assert_codec([], "x")


class TestResolution(unittest.TestCase):

    def test_pass(self):
        assert_resolution(parse_chunks([_chunk()]), width=1280, height=720)

    def test_fail(self):
        with self.assertRaises(WebcodecsAssertError):
            assert_resolution(
                parse_chunks([_chunk(width=640, height=360)]),
                width=1280, height=720,
            )

    def test_bad_args(self):
        with self.assertRaises(WebcodecsAssertError):
            assert_resolution([], width=0, height=0)


class TestKeyframe(unittest.TestCase):

    def test_pass(self):
        assert_keyframe_interval(parse_chunks([
            _chunk("key"), _chunk("delta"), _chunk("delta"),
            _chunk("key"), _chunk("delta"),
        ]), max_gap=3)

    def test_fail(self):
        with self.assertRaises(WebcodecsAssertError):
            assert_keyframe_interval(parse_chunks([
                _chunk("key"), _chunk("delta"), _chunk("delta"),
                _chunk("delta"), _chunk("delta"),
            ]), max_gap=2)

    def test_bad_gap(self):
        with self.assertRaises(WebcodecsAssertError):
            assert_keyframe_interval([], max_gap=0)


class TestFramerate(unittest.TestCase):

    def test_estimate(self):
        chunks = parse_chunks([
            _chunk("key", timestamp=0),
            _chunk("delta", timestamp=33_000),
            _chunk("delta", timestamp=66_000),
        ])
        self.assertAlmostEqual(estimate_framerate(chunks), 30.3, delta=1)

    def test_under_min(self):
        chunks = parse_chunks([
            _chunk("key", timestamp=0),
            _chunk("delta", timestamp=100_000),
        ])
        with self.assertRaises(WebcodecsAssertError):
            assert_framerate_at_least(chunks, min_fps=30)

    def test_short_returns_zero(self):
        self.assertEqual(estimate_framerate([]), 0)

    def test_bad_min(self):
        with self.assertRaises(WebcodecsAssertError):
            assert_framerate_at_least([], min_fps=0)


if __name__ == "__main__":
    unittest.main()
