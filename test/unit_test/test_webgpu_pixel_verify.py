"""Unit tests for je_web_runner.utils.webgpu_pixel_verify."""
import base64
import unittest

from je_web_runner.utils.webgpu_pixel_verify.pixel import (
    HARVEST_SCRIPT,
    WebgpuPixelVerifyError,
    assert_mean_in_band,
    assert_no_fully_transparent,
    assert_no_solid_color,
    assert_similar,
    mean_rgba,
    parse_frame,
    tile_diff_score,
)


def _solid(width, height, r, g, b, a):
    return bytes([r, g, b, a]) * (width * height)


def _payload(width, height, raw):
    return {
        "width": width, "height": height,
        "rgba_b64": base64.b64encode(raw).decode("ascii"),
    }


class TestParse(unittest.TestCase):

    def test_basic(self):
        raw = _solid(2, 2, 255, 0, 0, 255)
        f = parse_frame(_payload(2, 2, raw))
        self.assertEqual(f.width, 2)
        self.assertEqual(len(f.rgba), 16)

    def test_script_constant(self):
        self.assertIn("getContext('webgpu')", HARVEST_SCRIPT)

    def test_bad_payload(self):
        with self.assertRaises(WebgpuPixelVerifyError):
            parse_frame("nope")
  # NOSONAR python:S5655 - deliberate bad input
    def test_missing_dims(self):
        with self.assertRaises(WebgpuPixelVerifyError):
            parse_frame({"width": 1})

    def test_bad_dims(self):
        with self.assertRaises(WebgpuPixelVerifyError):
            parse_frame({"width": 0, "height": 1, "rgba_b64": ""})

    def test_bad_b64(self):
        with self.assertRaises(WebgpuPixelVerifyError):
            parse_frame({"width": 1, "height": 1, "rgba_b64": 123})

    def test_length_mismatch(self):
        with self.assertRaises(WebgpuPixelVerifyError):
            parse_frame(_payload(2, 2, b"x"))


class TestMean(unittest.TestCase):

    def test_solid(self):
        raw = _solid(2, 2, 100, 50, 25, 255)
        f = parse_frame(_payload(2, 2, raw))
        r, g, b, a = mean_rgba(f)
        self.assertEqual(int(r), 100)
        self.assertEqual(int(g), 50)
        self.assertEqual(int(b), 25)
        self.assertEqual(int(a), 255)


class TestMeanBand(unittest.TestCase):

    def test_pass(self):
        f = parse_frame(_payload(1, 1, _solid(1, 1, 100, 0, 0, 255)))
        assert_mean_in_band(f, channel="r", min_value=50, max_value=150)

    def test_fail(self):
        f = parse_frame(_payload(1, 1, _solid(1, 1, 100, 0, 0, 255)))
        with self.assertRaises(WebgpuPixelVerifyError):
            assert_mean_in_band(f, channel="r",
                                min_value=200, max_value=255)

    def test_bad_channel(self):
        f = parse_frame(_payload(1, 1, _solid(1, 1, 0, 0, 0, 255)))
        with self.assertRaises(WebgpuPixelVerifyError):
            assert_mean_in_band(f, channel="x",
                                min_value=0, max_value=255)

    def test_bad_bounds(self):
        f = parse_frame(_payload(1, 1, _solid(1, 1, 0, 0, 0, 255)))
        with self.assertRaises(WebgpuPixelVerifyError):
            assert_mean_in_band(f, channel="r",
                                min_value=255, max_value=0)


class TestTransparent(unittest.TestCase):

    def test_pass(self):
        f = parse_frame(_payload(1, 1, _solid(1, 1, 0, 0, 0, 255)))
        assert_no_fully_transparent(f)

    def test_fail(self):
        f = parse_frame(_payload(1, 1, _solid(1, 1, 0, 0, 0, 0)))
        with self.assertRaises(WebgpuPixelVerifyError):
            assert_no_fully_transparent(f)


class TestSolidColor(unittest.TestCase):

    def test_solid_raises(self):
        f = parse_frame(_payload(4, 4, _solid(4, 4, 10, 20, 30, 255)))
        with self.assertRaises(WebgpuPixelVerifyError):
            assert_no_solid_color(f)

    def test_varied_passes(self):
        raw = bytearray(_solid(4, 4, 10, 20, 30, 255))
        raw[4:8] = bytes([200, 100, 50, 255])   # one differing pixel
        f = parse_frame(_payload(4, 4, bytes(raw)))
        assert_no_solid_color(f)


class TestDiff(unittest.TestCase):

    def test_identical(self):
        f = parse_frame(_payload(4, 4, _solid(4, 4, 100, 100, 100, 255)))
        self.assertEqual(tile_diff_score(f, f), 0)

    def test_dim_mismatch(self):
        a = parse_frame(_payload(1, 1, _solid(1, 1, 0, 0, 0, 255)))
        b = parse_frame(_payload(2, 2, _solid(2, 2, 0, 0, 0, 255)))
        with self.assertRaises(WebgpuPixelVerifyError):
            tile_diff_score(a, b)

    def test_bad_tiles(self):
        f = parse_frame(_payload(1, 1, _solid(1, 1, 0, 0, 0, 255)))
        with self.assertRaises(WebgpuPixelVerifyError):
            tile_diff_score(f, f, tiles=0)

    def test_assert_similar_pass(self):
        f = parse_frame(_payload(4, 4, _solid(4, 4, 100, 100, 100, 255)))
        assert_similar(f, f)

    def test_assert_similar_fail(self):
        a = parse_frame(_payload(4, 4, _solid(4, 4, 0, 0, 0, 255)))
        b = parse_frame(_payload(4, 4, _solid(4, 4, 255, 255, 255, 255)))
        with self.assertRaises(WebgpuPixelVerifyError):
            assert_similar(a, b, max_diff=0.05)

    def test_bad_max_diff(self):
        f = parse_frame(_payload(1, 1, _solid(1, 1, 0, 0, 0, 255)))
        with self.assertRaises(WebgpuPixelVerifyError):
            assert_similar(f, f, max_diff=2)


if __name__ == "__main__":
    unittest.main()
