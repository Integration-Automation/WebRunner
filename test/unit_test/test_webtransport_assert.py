"""Unit tests for je_web_runner.utils.webtransport_assert."""
import json
import unittest

from je_web_runner.utils.webtransport_assert.streams import (
    DATAGRAM,
    RECEIVED,
    SENT,
    STREAM,
    WebTransportAssertError,
    WtFrame,
    WtFrameRecorder,
    assert_datagram_count,
    assert_json_shape,
    assert_payload_contains,
    assert_stream_complete,
    to_json,
)


class TestFrame(unittest.TestCase):

    def test_bad_direction(self):
        with self.assertRaises(WebTransportAssertError):
            WtFrame(direction="weird", channel=DATAGRAM, payload=b"x")

    def test_bad_channel(self):
        with self.assertRaises(WebTransportAssertError):
            WtFrame(direction=SENT, channel="weird", payload=b"x")

    def test_payload_must_be_bytes(self):
        with self.assertRaises(WebTransportAssertError):
            WtFrame(direction=SENT, channel=DATAGRAM, payload="text")  # type: ignore[arg-type]

    def test_stream_requires_id(self):
        with self.assertRaises(WebTransportAssertError):
            WtFrame(direction=SENT, channel=STREAM, payload=b"x")

    def test_as_text(self):
        f = WtFrame(direction=SENT, channel=DATAGRAM, payload=b"hello")
        self.assertEqual(f.as_text(), "hello")

    def test_as_json(self):
        f = WtFrame(direction=SENT, channel=DATAGRAM, payload=b'{"a":1}')
        self.assertEqual(f.as_json(), {"a": 1})

    def test_as_json_bad(self):
        f = WtFrame(direction=SENT, channel=DATAGRAM, payload=b"not json")
        with self.assertRaises(WebTransportAssertError):
            f.as_json()


class TestRecorder(unittest.TestCase):

    def test_records_datagrams(self):
        rec = WtFrameRecorder()
        rec.record_sent_datagram(b"hi")
        rec.record_received_datagram(b"bye")
        self.assertEqual(len(rec), 2)

    def test_records_stream_chunks(self):
        rec = WtFrameRecorder()
        rec.record_stream_chunk(RECEIVED, stream_id=1, payload=b"a")
        rec.record_stream_chunk(RECEIVED, stream_id=1, payload=b"b", fin=True)
        chunks = rec.frames(stream_id=1)
        self.assertEqual(len(chunks), 2)
        self.assertTrue(chunks[-1].fin)

    def test_clear(self):
        rec = WtFrameRecorder()
        rec.record_sent_datagram(b"x")
        rec.clear()
        self.assertEqual(len(rec), 0)

    def test_filter_combinations(self):
        rec = WtFrameRecorder()
        rec.record_sent_datagram(b"a")
        rec.record_received_datagram(b"b")
        rec.record_stream_chunk(SENT, stream_id=7, payload=b"c")
        self.assertEqual(len(rec.frames(channel=DATAGRAM)), 2)
        self.assertEqual(len(rec.frames(channel=STREAM)), 1)
        self.assertEqual(len(rec.frames(direction=SENT)), 2)
        self.assertEqual(rec.stream_ids(), [7])

    def test_filter_rejects_unknown(self):
        rec = WtFrameRecorder()
        with self.assertRaises(WebTransportAssertError):
            rec.frames(direction="x")
        with self.assertRaises(WebTransportAssertError):
            rec.frames(channel="x")

    def test_record_rejects_non_frame(self):
        with self.assertRaises(WebTransportAssertError):
            WtFrameRecorder().record("not a frame")  # type: ignore[arg-type]


class TestAssertDatagramCount(unittest.TestCase):

    def test_in_range(self):
        rec = WtFrameRecorder()
        rec.record_sent_datagram(b"a")
        rec.record_received_datagram(b"b")
        self.assertEqual(assert_datagram_count(rec, minimum=2), 2)

    def test_below_minimum(self):
        with self.assertRaises(WebTransportAssertError):
            assert_datagram_count(WtFrameRecorder(), minimum=1)

    def test_above_maximum(self):
        rec = WtFrameRecorder()
        rec.record_sent_datagram(b"a")
        rec.record_sent_datagram(b"b")
        with self.assertRaises(WebTransportAssertError):
            assert_datagram_count(rec, maximum=1)

    def test_filter_by_direction(self):
        rec = WtFrameRecorder()
        rec.record_sent_datagram(b"a")
        rec.record_received_datagram(b"b")
        self.assertEqual(
            assert_datagram_count(rec, direction=SENT, minimum=1, maximum=1), 1,
        )

    def test_max_lt_min_rejected(self):
        with self.assertRaises(WebTransportAssertError):
            assert_datagram_count(WtFrameRecorder(), minimum=3, maximum=1)


class TestAssertStreamComplete(unittest.TestCase):

    def test_pass(self):
        rec = WtFrameRecorder()
        rec.record_stream_chunk(RECEIVED, stream_id=1, payload=b"hello ")
        rec.record_stream_chunk(RECEIVED, stream_id=1, payload=b"world", fin=True)
        self.assertEqual(assert_stream_complete(rec, 1), b"hello world")

    def test_missing_stream(self):
        with self.assertRaises(WebTransportAssertError):
            assert_stream_complete(WtFrameRecorder(), 1)

    def test_no_fin(self):
        rec = WtFrameRecorder()
        rec.record_stream_chunk(RECEIVED, stream_id=1, payload=b"x")
        with self.assertRaises(WebTransportAssertError):
            assert_stream_complete(rec, 1)

    def test_bad_direction(self):
        with self.assertRaises(WebTransportAssertError):
            assert_stream_complete(WtFrameRecorder(), 1, direction="weird")


class TestAssertPayloadContains(unittest.TestCase):

    def test_match(self):
        rec = WtFrameRecorder()
        rec.record_received_datagram(b"hello world")
        self.assertIsNotNone(assert_payload_contains(rec, b"world"))

    def test_miss(self):
        with self.assertRaises(WebTransportAssertError):
            assert_payload_contains(WtFrameRecorder(), b"x")

    def test_empty_needle(self):
        with self.assertRaises(WebTransportAssertError):
            assert_payload_contains(WtFrameRecorder(), b"")


class TestAssertJsonShape(unittest.TestCase):

    def test_match(self):
        rec = WtFrameRecorder()
        rec.record_received_datagram(b'{"id":1,"v":2}')
        assert_json_shape(rec, ["id", "v"])

    def test_miss(self):
        rec = WtFrameRecorder()
        rec.record_received_datagram(b'{"id":1}')
        with self.assertRaises(WebTransportAssertError):
            assert_json_shape(rec, ["id", "missing"])

    def test_empty_keys(self):
        with self.assertRaises(WebTransportAssertError):
            assert_json_shape(WtFrameRecorder(), [])


class TestToJson(unittest.TestCase):

    def test_roundtrip(self):
        rec = WtFrameRecorder()
        rec.record_sent_datagram(b"hi")
        loaded = json.loads(to_json(rec.frames()))
        self.assertEqual(loaded[0]["payload_b64"], "6869")  # 'hi' hex


if __name__ == "__main__":
    unittest.main()
