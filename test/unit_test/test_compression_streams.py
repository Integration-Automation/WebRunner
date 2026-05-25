"""Unit tests for je_web_runner.utils.compression_streams."""
import gzip
import unittest
import zlib

from je_web_runner.utils.compression_streams.streams import (
    Algorithm,
    CompressionStreamsError,
    HARVEST_SCRIPT,
    assert_ratio_under,
    assert_round_trip,
    compression_ratio,
    decompress,
)


PAYLOAD = b"the quick brown fox jumps over the lazy dog" * 100


class TestScript(unittest.TestCase):

    def test_contains(self):
        self.assertIn("CompressionStream", HARVEST_SCRIPT)


class TestDecompress(unittest.TestCase):

    def test_gzip(self):
        self.assertEqual(decompress(gzip.compress(PAYLOAD), Algorithm.GZIP),
                         PAYLOAD)

    def test_deflate(self):
        self.assertEqual(decompress(zlib.compress(PAYLOAD), Algorithm.DEFLATE),
                         PAYLOAD)

    def test_deflate_raw(self):
        co = zlib.compressobj(wbits=-zlib.MAX_WBITS)
        raw = co.compress(PAYLOAD) + co.flush()
        self.assertEqual(decompress(raw, Algorithm.DEFLATE_RAW), PAYLOAD)

    def test_gzip_bad(self):
        with self.assertRaises(CompressionStreamsError):
            decompress(b"not gzip", Algorithm.GZIP)

    def test_deflate_bad(self):
        with self.assertRaises(CompressionStreamsError):
            decompress(b"not zlib", Algorithm.DEFLATE)

    def test_deflate_raw_bad(self):
        with self.assertRaises(CompressionStreamsError):
            decompress(b"x", Algorithm.DEFLATE_RAW)

    def test_bad_data_type(self):
        with self.assertRaises(CompressionStreamsError):
            decompress("nope", Algorithm.GZIP)

    def test_bad_algorithm_type(self):
        with self.assertRaises(CompressionStreamsError):
            decompress(b"x", "gzip")


class TestRoundTrip(unittest.TestCase):

    def test_pass(self):
        assert_round_trip(
            original=PAYLOAD,
            compressed=gzip.compress(PAYLOAD),
            algorithm=Algorithm.GZIP,
        )

    def test_fail(self):
        with self.assertRaises(CompressionStreamsError):
            assert_round_trip(
                original=PAYLOAD,
                compressed=gzip.compress(b"different"),
                algorithm=Algorithm.GZIP,
            )

    def test_bad_original(self):
        with self.assertRaises(CompressionStreamsError):
            assert_round_trip(
                original="nope", compressed=b"", algorithm=Algorithm.GZIP,
            )


class TestRatio(unittest.TestCase):

    def test_pass(self):
        assert_ratio_under(
            original_size=1000, compressed_size=200, max_ratio=0.5,
        )

    def test_fail(self):
        with self.assertRaises(CompressionStreamsError):
            assert_ratio_under(
                original_size=1000, compressed_size=900, max_ratio=0.5,
            )

    def test_bad_max(self):
        with self.assertRaises(CompressionStreamsError):
            assert_ratio_under(
                original_size=1, compressed_size=1, max_ratio=2,
            )

    def test_compute_bad_size(self):
        with self.assertRaises(CompressionStreamsError):
            compression_ratio(0, 100)


if __name__ == "__main__":
    unittest.main()
