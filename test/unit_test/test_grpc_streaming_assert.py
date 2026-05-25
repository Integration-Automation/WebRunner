"""Unit tests for je_web_runner.utils.grpc_streaming_assert."""
import unittest

from je_web_runner.utils.grpc_streaming_assert.assertions import (
    GrpcStreamingAssertError,
    Mode,
    StatusCode,
    StreamFrame,
    StreamRecord,
    assert_frame_count_between,
    assert_frames_in_order,
    assert_half_close_before_final,
    assert_max_frame_size,
    assert_no_deadline_exceeded,
    assert_status,
    parse_record,
)


def _frame(size=10, **body):
    return {"payload_size": size, "body": body, "direction": "in", "ts_ms": 0}


class TestParse(unittest.TestCase):

    def test_basic(self):
        rec = parse_record({
            "method": "/svc/Method", "mode": "server_stream",
            "frames": [_frame(seq=0), _frame(seq=1)],
            "status": "OK", "duration_ms": 50,
        })
        self.assertEqual(rec.mode, Mode.SERVER_STREAM)
        self.assertEqual(len(rec.frames), 2)

    def test_unknown_mode(self):
        with self.assertRaises(GrpcStreamingAssertError):
            parse_record({"mode": "weird"})

    def test_unknown_status(self):
        with self.assertRaises(GrpcStreamingAssertError):
            parse_record({"status": "WEIRD"})

    def test_non_dict(self):
        with self.assertRaises(GrpcStreamingAssertError):
            parse_record("nope")

    def test_skips_non_dict_frames(self):
        rec = parse_record({"frames": ["string", _frame(seq=0)]})
        self.assertEqual(len(rec.frames), 1)


class TestStatus(unittest.TestCase):

    def test_pass(self):
        assert_status(StreamRecord("m", Mode.UNARY,
                                   status=StatusCode.OK), StatusCode.OK)

    def test_fail(self):
        with self.assertRaises(GrpcStreamingAssertError):
            assert_status(StreamRecord("m", Mode.UNARY,
                                       status=StatusCode.INTERNAL),
                          StatusCode.OK)


class TestFrameCount(unittest.TestCase):

    def test_pass(self):
        rec = StreamRecord("m", Mode.SERVER_STREAM,
                           frames=[StreamFrame() for _ in range(3)])
        assert_frame_count_between(rec, min_count=1, max_count=5)

    def test_fail_high(self):
        rec = StreamRecord("m", Mode.SERVER_STREAM,
                           frames=[StreamFrame() for _ in range(10)])
        with self.assertRaises(GrpcStreamingAssertError):
            assert_frame_count_between(rec, min_count=0, max_count=5)

    def test_fail_low(self):
        rec = StreamRecord("m", Mode.SERVER_STREAM, frames=[])
        with self.assertRaises(GrpcStreamingAssertError):
            assert_frame_count_between(rec, min_count=1, max_count=5)

    def test_bad_bounds(self):
        with self.assertRaises(GrpcStreamingAssertError):
            assert_frame_count_between(
                StreamRecord("m", Mode.UNARY), min_count=5, max_count=1,
            )


class TestFrameSize(unittest.TestCase):

    def test_pass(self):
        rec = StreamRecord("m", Mode.UNARY,
                           frames=[StreamFrame(payload_size=100)])
        assert_max_frame_size(rec, max_bytes=200)

    def test_fail(self):
        rec = StreamRecord("m", Mode.UNARY,
                           frames=[StreamFrame(payload_size=999)])
        with self.assertRaises(GrpcStreamingAssertError):
            assert_max_frame_size(rec, max_bytes=200)

    def test_bad_max(self):
        with self.assertRaises(GrpcStreamingAssertError):
            assert_max_frame_size(StreamRecord("m", Mode.UNARY), max_bytes=0)


class TestOrder(unittest.TestCase):

    def test_pass(self):
        rec = StreamRecord("m", Mode.SERVER_STREAM, frames=[
            StreamFrame(body={"seq": 0}),
            StreamFrame(body={"seq": 1}),
        ])
        assert_frames_in_order(rec, key="seq", expected=[0, 1])

    def test_fail(self):
        rec = StreamRecord("m", Mode.SERVER_STREAM, frames=[
            StreamFrame(body={"seq": 1}),
            StreamFrame(body={"seq": 0}),
        ])
        with self.assertRaises(GrpcStreamingAssertError):
            assert_frames_in_order(rec, key="seq", expected=[0, 1])


class TestDeadline(unittest.TestCase):

    def test_pass(self):
        assert_no_deadline_exceeded(StreamRecord(
            "m", Mode.UNARY, status=StatusCode.OK,
        ))

    def test_fail(self):
        with self.assertRaises(GrpcStreamingAssertError):
            assert_no_deadline_exceeded(StreamRecord(
                "m", Mode.UNARY, status=StatusCode.DEADLINE_EXCEEDED,
            ))


class TestHalfClose(unittest.TestCase):

    def test_pass(self):
        rec = StreamRecord("m", Mode.BIDI, frames=[
            StreamFrame(direction="in", ts_ms=100),
        ], half_closed_ts_ms=50)
        assert_half_close_before_final(rec)

    def test_fail_after_last(self):
        rec = StreamRecord("m", Mode.BIDI, frames=[
            StreamFrame(direction="in", ts_ms=100),
        ], half_closed_ts_ms=200)
        with self.assertRaises(GrpcStreamingAssertError):
            assert_half_close_before_final(rec)

    def test_never_half_closed(self):
        with self.assertRaises(GrpcStreamingAssertError):
            assert_half_close_before_final(StreamRecord("m", Mode.BIDI))

    def test_wrong_mode(self):
        with self.assertRaises(GrpcStreamingAssertError):
            assert_half_close_before_final(StreamRecord("m", Mode.UNARY,
                                                        half_closed_ts_ms=1))


if __name__ == "__main__":
    unittest.main()
