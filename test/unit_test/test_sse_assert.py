"""Unit tests for je_web_runner.utils.sse_assert."""
import json
import unittest

from je_web_runner.utils.sse_assert.stream import (
    SseAssertError,
    SseEvent,
    SseRecorder,
    assert_data_contains,
    assert_event_count,
    assert_json_shape,
    assert_received_event,
    assert_strictly_increasing_ids,
    parse_sse_stream,
    to_json,
)


class TestParse(unittest.TestCase):

    def test_basic_event(self):
        stream = "data: hello\n\n"
        events = parse_sse_stream(stream)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event, "message")
        self.assertEqual(events[0].data, "hello")

    def test_event_type(self):
        stream = "event: ping\ndata: 1\n\n"
        events = parse_sse_stream(stream)
        self.assertEqual(events[0].event, "ping")

    def test_id_and_retry(self):
        stream = "id: 42\nretry: 1500\ndata: x\n\n"
        events = parse_sse_stream(stream)
        self.assertEqual(events[0].id, "42")
        self.assertEqual(events[0].retry, 1500)

    def test_multiline_data(self):
        stream = "data: line one\ndata: line two\n\n"
        events = parse_sse_stream(stream)
        self.assertEqual(events[0].data, "line one\nline two")

    def test_comment_ignored(self):
        stream = ": keep-alive\ndata: real\n\n"
        events = parse_sse_stream(stream)
        self.assertEqual(events[0].data, "real")

    def test_crlf_normalised(self):
        stream = "data: r\r\n\r\n"
        events = parse_sse_stream(stream)
        self.assertEqual(events[0].data, "r")

    def test_multiple_events(self):
        stream = "data: a\n\ndata: b\n\ndata: c\n\n"
        events = parse_sse_stream(stream)
        self.assertEqual([e.data for e in events], ["a", "b", "c"])

    def test_empty_returns_empty(self):
        self.assertEqual(parse_sse_stream("\n\n\n"), [])

    def test_rejects_non_string(self):
        with self.assertRaises(SseAssertError):
            parse_sse_stream(123)  # type: ignore[arg-type]  # NOSONAR S5655 — intentional bad-input test


class TestRecorder(unittest.TestCase):

    def test_feed_complete_event(self):
        rec = SseRecorder()
        n = rec.feed("data: hello\n\n")
        self.assertEqual(n, 1)
        self.assertEqual(len(rec), 1)

    def test_feed_partial_then_complete(self):
        rec = SseRecorder()
        self.assertEqual(rec.feed("data: hel"), 0)
        self.assertEqual(rec.feed("lo\n\n"), 1)
        self.assertEqual(rec.events()[0].data, "hello")

    def test_feed_event_helper(self):
        rec = SseRecorder()
        rec.feed_event(SseEvent(event="msg", data="x"))
        self.assertEqual(len(rec), 1)

    def test_clear(self):
        rec = SseRecorder()
        rec.feed("data: a\n\n")
        rec.clear()
        self.assertEqual(len(rec), 0)

    def test_filter_by_event_type(self):
        rec = SseRecorder()
        rec.feed("event: ping\ndata: 1\n\nevent: pong\ndata: 2\n\n")
        self.assertEqual(len(rec.events(event_type="ping")), 1)

    def test_rejects_non_string_chunk(self):
        with self.assertRaises(SseAssertError):
            SseRecorder().feed(123)  # type: ignore[arg-type]  # NOSONAR S5655 — intentional bad-input test


class TestAssertCount(unittest.TestCase):

    def test_in_range(self):
        rec = SseRecorder()
        rec.feed("data: a\n\ndata: b\n\n")
        self.assertEqual(assert_event_count(rec, minimum=2, maximum=5), 2)

    def test_below_minimum(self):
        with self.assertRaises(SseAssertError):
            assert_event_count(SseRecorder(), minimum=1)

    def test_above_maximum(self):
        rec = SseRecorder()
        rec.feed("data: a\n\ndata: b\n\n")
        with self.assertRaises(SseAssertError):
            assert_event_count(rec, maximum=1)

    def test_filter_by_event_type(self):
        rec = SseRecorder()
        rec.feed("event: ping\ndata: 1\n\nevent: pong\ndata: 2\n\n")
        self.assertEqual(assert_event_count(rec, event_type="ping", minimum=1, maximum=1), 1)


class TestAssertReceived(unittest.TestCase):

    def test_match(self):
        rec = SseRecorder()
        rec.feed("data: success\n\n")
        e = assert_received_event(rec, lambda e: "success" in e.data)
        self.assertEqual(e.data, "success")

    def test_no_match(self):
        rec = SseRecorder()
        rec.feed("data: x\n\n")
        with self.assertRaises(SseAssertError):
            assert_received_event(rec, lambda e: False)


class TestAssertDataContains(unittest.TestCase):

    def test_match(self):
        rec = SseRecorder()
        rec.feed("data: hello world\n\n")
        e = assert_data_contains(rec, "world")
        self.assertEqual(e.data, "hello world")

    def test_miss(self):
        with self.assertRaises(SseAssertError):
            assert_data_contains(SseRecorder(), "x")

    def test_empty_needle(self):
        with self.assertRaises(SseAssertError):
            assert_data_contains(SseRecorder(), "")


class TestAssertJsonShape(unittest.TestCase):

    def test_match(self):
        rec = SseRecorder()
        rec.feed('data: {"id":1,"v":2}\n\n')
        e = assert_json_shape(rec, ["id", "v"])
        self.assertEqual(e.as_json()["id"], 1)

    def test_missing_key(self):
        rec = SseRecorder()
        rec.feed('data: {"id":1}\n\n')
        with self.assertRaises(SseAssertError):
            assert_json_shape(rec, ["id", "missing"])

    def test_non_json_skipped(self):
        rec = SseRecorder()
        rec.feed("data: not json\n\ndata: {\"k\":true}\n\n")
        assert_json_shape(rec, ["k"])

    def test_empty_keys_rejected(self):
        with self.assertRaises(SseAssertError):
            assert_json_shape(SseRecorder(), [])


class TestStrictlyIncreasing(unittest.TestCase):

    def test_pass(self):
        rec = SseRecorder()
        rec.feed("id: a\ndata: 1\n\nid: b\ndata: 2\n\n")
        assert_strictly_increasing_ids(rec)

    def test_fail_on_duplicate(self):
        rec = SseRecorder()
        rec.feed("id: a\ndata: 1\n\nid: a\ndata: 2\n\n")
        with self.assertRaises(SseAssertError):
            assert_strictly_increasing_ids(rec)


class TestToJson(unittest.TestCase):

    def test_roundtrip(self):
        rec = SseRecorder()
        rec.feed("data: hi\n\n")
        loaded = json.loads(to_json(rec.events()))
        self.assertEqual(loaded[0]["data"], "hi")


if __name__ == "__main__":
    unittest.main()
