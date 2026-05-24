"""Unit tests for je_web_runner.utils.websocket_assert."""
import json
import re
import unittest

from je_web_runner.utils.websocket_assert.frames import (
    RECEIVED,
    SENT,
    WebSocketAssertError,
    WsFrame,
    WsFrameRecorder,
    assert_frame_count,
    assert_frame_received,
    assert_json_shape,
    assert_payload_contains,
    assert_pubsub_pattern,
    to_json,
)


def _recorder_with(*frames):
    rec = WsFrameRecorder()
    for f in frames:
        rec.record(f)
    return rec


class TestFrame(unittest.TestCase):

    def test_rejects_bad_direction(self):
        with self.assertRaises(WebSocketAssertError):
            WsFrame(direction="weird", url="ws://x", payload="")

    def test_as_json_decodes(self):
        f = WsFrame(direction=SENT, url="ws://x", payload='{"a":1}')
        self.assertEqual(f.as_json(), {"a": 1})

    def test_as_json_raises_on_bad(self):
        f = WsFrame(direction=SENT, url="ws://x", payload="not json")
        with self.assertRaises(WebSocketAssertError):
            f.as_json()


class TestRecorder(unittest.TestCase):

    def test_helpers_record_with_direction(self):
        rec = WsFrameRecorder()
        rec.record_sent("ws://x", "hi")
        rec.record_received("ws://x", "bye")
        self.assertEqual(len(rec), 2)
        self.assertEqual(rec.frames()[0].direction, SENT)
        self.assertEqual(rec.frames()[1].direction, RECEIVED)

    def test_filter_by_direction(self):
        rec = WsFrameRecorder()
        rec.record_sent("ws://x", "a")
        rec.record_received("ws://x", "b")
        self.assertEqual(len(rec.frames(direction=SENT)), 1)
        self.assertEqual(len(rec.frames(direction=RECEIVED)), 1)

    def test_filter_by_url(self):
        rec = WsFrameRecorder()
        rec.record_sent("ws://api/sub", "a")
        rec.record_sent("ws://api/other", "b")
        self.assertEqual(len(rec.frames(url_match="sub")), 1)
        self.assertEqual(len(rec.frames(url_match=re.compile(r"/api/.+"))), 2)

    def test_clear(self):
        rec = WsFrameRecorder()
        rec.record_sent("ws://x", "a")
        rec.clear()
        self.assertEqual(len(rec), 0)

    def test_record_rejects_non_frame(self):
        rec = WsFrameRecorder()
        with self.assertRaises(WebSocketAssertError):
            rec.record("string payload")  # type: ignore[arg-type]


class TestAssertCount(unittest.TestCase):

    def test_in_range(self):
        rec = _recorder_with(
            WsFrame(SENT, "ws://x", "a"),
            WsFrame(RECEIVED, "ws://x", "b"),
        )
        self.assertEqual(assert_frame_count(rec, minimum=2, maximum=5), 2)

    def test_below_minimum(self):
        rec = WsFrameRecorder()
        with self.assertRaises(WebSocketAssertError):
            assert_frame_count(rec, minimum=1)

    def test_above_maximum(self):
        rec = _recorder_with(WsFrame(SENT, "ws://x", "a"), WsFrame(SENT, "ws://x", "b"))
        with self.assertRaises(WebSocketAssertError):
            assert_frame_count(rec, maximum=1)

    def test_negative_minimum_rejected(self):
        with self.assertRaises(WebSocketAssertError):
            assert_frame_count(WsFrameRecorder(), minimum=-1)

    def test_max_lt_min_rejected(self):
        with self.assertRaises(WebSocketAssertError):
            assert_frame_count(WsFrameRecorder(), minimum=3, maximum=1)


class TestAssertReceived(unittest.TestCase):

    def test_finds_match(self):
        rec = _recorder_with(
            WsFrame(RECEIVED, "ws://x", '{"type":"ack"}'),
        )
        f = assert_frame_received(rec, lambda fr: "ack" in fr.payload, description="ack")
        self.assertIn("ack", f.payload)

    def test_no_match(self):
        rec = _recorder_with(WsFrame(RECEIVED, "ws://x", "nope"))
        with self.assertRaises(WebSocketAssertError):
            assert_frame_received(rec, lambda fr: False)

    def test_predicate_exception_treated_as_no_match(self):
        rec = _recorder_with(WsFrame(RECEIVED, "ws://x", "a"))

        def bad(_):
            raise RuntimeError("oops")
        with self.assertRaises(WebSocketAssertError):
            assert_frame_received(rec, bad)


class TestAssertPayloadContains(unittest.TestCase):

    def test_match(self):
        rec = _recorder_with(WsFrame(SENT, "ws://x", "hello world"))
        f = assert_payload_contains(rec, "world")
        self.assertEqual(f.direction, SENT)

    def test_miss(self):
        rec = _recorder_with(WsFrame(SENT, "ws://x", "hello"))
        with self.assertRaises(WebSocketAssertError):
            assert_payload_contains(rec, "missing")

    def test_empty_needle_rejected(self):
        with self.assertRaises(WebSocketAssertError):
            assert_payload_contains(WsFrameRecorder(), "")


class TestAssertJsonShape(unittest.TestCase):

    def test_found(self):
        rec = _recorder_with(WsFrame(RECEIVED, "ws://x", '{"id":1,"v":2}'))
        f = assert_json_shape(rec, ["id", "v"])
        self.assertEqual(f.as_json()["id"], 1)

    def test_missing_key(self):
        rec = _recorder_with(WsFrame(RECEIVED, "ws://x", '{"id":1}'))
        with self.assertRaises(WebSocketAssertError):
            assert_json_shape(rec, ["id", "missing"])

    def test_non_json_frames_skipped(self):
        rec = _recorder_with(
            WsFrame(RECEIVED, "ws://x", "not json"),
            WsFrame(RECEIVED, "ws://x", '{"k":true}'),
        )
        assert_json_shape(rec, ["k"])

    def test_empty_keys_rejected(self):
        with self.assertRaises(WebSocketAssertError):
            assert_json_shape(WsFrameRecorder(), [])


class TestAssertPubsub(unittest.TestCase):

    def test_subscribe_then_publish(self):
        rec = _recorder_with(
            WsFrame(SENT, "ws://x", '{"op":"subscribe","ch":"prices"}'),
            WsFrame(RECEIVED, "ws://x", '{"ch":"prices","data":1}'),
        )
        assert_pubsub_pattern(
            rec,
            subscribe_matcher=lambda f: '"subscribe"' in f.payload,
            publish_matcher=lambda f: '"data":1' in f.payload,
        )

    def test_publish_before_subscribe_fails(self):
        rec = _recorder_with(
            WsFrame(RECEIVED, "ws://x", '{"data":1}'),
            WsFrame(SENT, "ws://x", '{"op":"subscribe"}'),
        )
        with self.assertRaises(WebSocketAssertError):
            assert_pubsub_pattern(
                rec,
                subscribe_matcher=lambda f: "subscribe" in f.payload,
                publish_matcher=lambda f: "data" in f.payload,
            )

    def test_no_pair_at_all(self):
        with self.assertRaises(WebSocketAssertError):
            assert_pubsub_pattern(
                WsFrameRecorder(),
                subscribe_matcher=lambda f: True,
                publish_matcher=lambda f: True,
            )


class TestToJson(unittest.TestCase):

    def test_roundtrip(self):
        rec = _recorder_with(WsFrame(SENT, "ws://x", "hi"))
        text = to_json(rec.frames())
        loaded = json.loads(text)
        self.assertEqual(loaded[0]["payload"], "hi")


if __name__ == "__main__":
    unittest.main()
