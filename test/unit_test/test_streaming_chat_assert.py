"""Unit tests for je_web_runner.utils.streaming_chat_assert."""
import unittest

from je_web_runner.utils.streaming_chat_assert.stream import (
    StreamingChatAssertError,
    TokenDelta,
    assemble,
    assert_assembled_contains,
    assert_no_dup_or_oos,
    assert_no_stall,
    assert_ttft_under,
    assert_utf8_clean,
    max_inter_token_gap_ms,
    parse_deltas,
    time_to_first_token,
)


class TestDelta(unittest.TestCase):

    def test_basic(self):
        TokenDelta(text="x", ts_ms=10)

    def test_bad_text(self):
        with self.assertRaises(StreamingChatAssertError):
            TokenDelta(text=123)

    def test_bad_ts(self):
        with self.assertRaises(StreamingChatAssertError):
            TokenDelta(text="x", ts_ms=-1)


class TestParse(unittest.TestCase):

    def test_basic(self):
        d = parse_deltas([{"text": "hi", "ts_ms": 100}])
        self.assertEqual(d[0].text, "hi")

    def test_skip_non_dict(self):
        self.assertEqual(parse_deltas(["x"]), [])

    def test_bad_payload(self):
        with self.assertRaises(StreamingChatAssertError):
            parse_deltas("nope")


class TestAssemble(unittest.TestCase):

    def test_basic(self):
        self.assertEqual(
            assemble([TokenDelta(text="he"), TokenDelta(text="llo")]),
            "hello",
        )


class TestTTFT(unittest.TestCase):

    def test_compute(self):
        ttft = time_to_first_token([
            TokenDelta(text="", ts_ms=0),
            TokenDelta(text="hi", ts_ms=200),
        ])
        self.assertEqual(ttft, 200)

    def test_no_text(self):
        with self.assertRaises(StreamingChatAssertError):
            time_to_first_token([TokenDelta(text="", ts_ms=5)])

    def test_pass(self):
        assert_ttft_under([TokenDelta(text="x", ts_ms=100)], max_ms=1000)

    def test_fail(self):
        with self.assertRaises(StreamingChatAssertError):
            assert_ttft_under([TokenDelta(text="x", ts_ms=2000)], max_ms=1000)

    def test_bad_max(self):
        with self.assertRaises(StreamingChatAssertError):
            assert_ttft_under([], max_ms=0)


class TestGap(unittest.TestCase):

    def test_pass(self):
        assert_no_stall([
            TokenDelta(text="a", ts_ms=0),
            TokenDelta(text="b", ts_ms=500),
        ], max_gap_ms=1000)

    def test_fail(self):
        with self.assertRaises(StreamingChatAssertError):
            assert_no_stall([
                TokenDelta(text="a", ts_ms=0),
                TokenDelta(text="b", ts_ms=5000),
            ], max_gap_ms=1000)

    def test_max_gap_empty(self):
        self.assertEqual(max_inter_token_gap_ms([]), 0)


class TestAssembledContains(unittest.TestCase):

    def test_pass(self):
        assert_assembled_contains([TokenDelta(text="hello")], expected="ell")

    def test_fail(self):
        with self.assertRaises(StreamingChatAssertError):
            assert_assembled_contains([TokenDelta(text="hi")], expected="ello")

    def test_empty_expected(self):
        with self.assertRaises(StreamingChatAssertError):
            assert_assembled_contains([], expected="")


class TestUtf8(unittest.TestCase):

    def test_pass(self):
        assert_utf8_clean([TokenDelta(text="hello")])

    def test_fail(self):
        with self.assertRaises(StreamingChatAssertError):
            assert_utf8_clean([TokenDelta(text="x�y")])


class TestNoDup(unittest.TestCase):

    def test_pass(self):
        assert_no_dup_or_oos([
            TokenDelta(text="a", seq=1),
            TokenDelta(text="b", seq=2),
        ])

    def test_dup(self):
        with self.assertRaises(StreamingChatAssertError):
            assert_no_dup_or_oos([
                TokenDelta(text="a", seq=1),
                TokenDelta(text="b", seq=1),
            ])

    def test_oos(self):
        with self.assertRaises(StreamingChatAssertError):
            assert_no_dup_or_oos([
                TokenDelta(text="a", seq=2),
                TokenDelta(text="b", seq=1),
            ])

    def test_no_seq(self):
        assert_no_dup_or_oos([TokenDelta(text="x")])


if __name__ == "__main__":
    unittest.main()
