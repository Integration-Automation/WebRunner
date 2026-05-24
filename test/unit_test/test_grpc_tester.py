"""Unit tests for je_web_runner.utils.grpc_tester."""
import unittest

from je_web_runner.utils.grpc_tester.client import (
    GrpcCall,
    GrpcCallRecorder,
    GrpcStatus,
    GrpcTesterError,
    assert_call_fails,
    assert_call_ok,
    assert_called,
    call,
    decode_grpc_web_message,
    encode_grpc_web_message,
    parse_trailer,
)


class TestRecorder(unittest.TestCase):

    def test_record_and_clear(self):
        rec = GrpcCallRecorder()
        rec.record(GrpcCall(method="Svc/Foo", request={}, response={},
                            status=GrpcStatus.OK, duration_ms=1))
        self.assertEqual(len(rec), 1)
        rec.clear()
        self.assertEqual(len(rec), 0)

    def test_filter_by_method(self):
        rec = GrpcCallRecorder()
        rec.record(GrpcCall("Svc/A", {}, {}, GrpcStatus.OK, 1))
        rec.record(GrpcCall("Svc/B", {}, {}, GrpcStatus.OK, 1))
        self.assertEqual(len(rec.calls(method="Svc/A")), 1)

    def test_filter_by_status(self):
        rec = GrpcCallRecorder()
        rec.record(GrpcCall("Svc/A", {}, {}, GrpcStatus.OK, 1))
        rec.record(GrpcCall("Svc/A", {}, {}, GrpcStatus.NOT_FOUND, 1))
        self.assertEqual(len(rec.calls(status=GrpcStatus.NOT_FOUND)), 1)

    def test_rejects_non_call(self):
        with self.assertRaises(GrpcTesterError):
            GrpcCallRecorder().record("not a call")  # type: ignore[arg-type]


class TestCallWrapper(unittest.TestCase):

    def test_success(self):
        def stub(request, **kwargs):
            return {"hello": request}
        rec = GrpcCallRecorder()
        result = call("Svc/Greet", stub, "world", recorder=rec)
        self.assertEqual(result.status, GrpcStatus.OK)
        self.assertEqual(result.response, {"hello": "world"})
        self.assertEqual(len(rec), 1)

    def test_failure_recorded(self):
        class FakeError(Exception):
            def code(self):
                return GrpcStatus.NOT_FOUND
        def stub(_request, **_kwargs):
            raise FakeError("missing")
        result = call("Svc/Get", stub, {})
        self.assertEqual(result.status, GrpcStatus.NOT_FOUND)
        self.assertIn("missing", result.error or "")

    def test_failure_unknown_status(self):
        def stub(_request, **_kwargs):
            raise RuntimeError("boom")
        self.assertEqual(call("Svc/X", stub, {}).status, GrpcStatus.UNKNOWN)

    def test_metadata_and_timeout_forwarded(self):
        seen: dict = {}
        def stub(request, **kwargs):
            seen.update(kwargs)
            return "ok"
        call("Svc/X", stub, "r", metadata=[("auth", "Bearer x")], timeout=5.0)
        self.assertEqual(seen["metadata"], [("auth", "Bearer x")])
        self.assertEqual(seen["timeout"], 5.0)

    def test_method_required(self):
        with self.assertRaises(GrpcTesterError):
            call("", lambda r, **k: None, {})

    def test_stub_must_be_callable(self):
        with self.assertRaises(GrpcTesterError):
            call("X", "not callable", {})  # type: ignore[arg-type]

    def test_status_with_tuple(self):
        class FakeCode:
            value = (5, "NOT_FOUND")
        class Err(Exception):
            def code(self):
                return FakeCode()
        def stub(_r, **_k):
            raise Err()
        self.assertEqual(call("Svc/X", stub, {}).status, GrpcStatus.NOT_FOUND)


class TestGrpcWebFraming(unittest.TestCase):

    def test_round_trip_single_message(self):
        framed = encode_grpc_web_message(b"hello")
        decoded = decode_grpc_web_message(framed)
        self.assertEqual(decoded, [(0, b"hello")])

    def test_decode_multiple_messages(self):
        framed = encode_grpc_web_message(b"a") + encode_grpc_web_message(b"bb")
        decoded = decode_grpc_web_message(framed)
        self.assertEqual([d[1] for d in decoded], [b"a", b"bb"])

    def test_encode_requires_bytes(self):
        with self.assertRaises(GrpcTesterError):
            encode_grpc_web_message("text")  # type: ignore[arg-type]

    def test_decode_requires_bytes(self):
        with self.assertRaises(GrpcTesterError):
            decode_grpc_web_message("text")  # type: ignore[arg-type]

    def test_truncated(self):
        with self.assertRaises(GrpcTesterError):
            decode_grpc_web_message(b"\x00\x00")

    def test_length_overrun(self):
        with self.assertRaises(GrpcTesterError):
            decode_grpc_web_message(b"\x00\x00\x00\x00\xffshort")


class TestParseTrailer(unittest.TestCase):

    def test_parses(self):
        trailer = b"grpc-status:5\r\ngrpc-message:not found\r\n"
        parsed = parse_trailer(trailer)
        self.assertEqual(parsed["grpc-status"], "5")
        self.assertEqual(parsed["grpc-message"], "not found")

    def test_rejects_non_bytes(self):
        with self.assertRaises(GrpcTesterError):
            parse_trailer("text")  # type: ignore[arg-type]

    def test_ignores_empty_lines(self):
        self.assertEqual(parse_trailer(b"\r\n\r\n"), {})


class TestAssertions(unittest.TestCase):

    def _ok(self):
        return GrpcCall("X", {}, {}, GrpcStatus.OK, 1)

    def _fail(self):
        return GrpcCall("X", {}, {}, GrpcStatus.NOT_FOUND, 1, error="missing")

    def test_assert_call_ok_pass(self):
        assert_call_ok(self._ok())

    def test_assert_call_ok_fail(self):
        with self.assertRaises(GrpcTesterError):
            assert_call_ok(self._fail())

    def test_assert_call_ok_rejects_non_call(self):
        with self.assertRaises(GrpcTesterError):
            assert_call_ok("nope")  # type: ignore[arg-type]

    def test_assert_call_fails_pass(self):
        assert_call_fails(self._fail(), status=GrpcStatus.NOT_FOUND)

    def test_assert_call_fails_wrong_code(self):
        with self.assertRaises(GrpcTesterError):
            assert_call_fails(self._fail(), status=GrpcStatus.PERMISSION_DENIED)

    def test_assert_call_fails_bad_status(self):
        with self.assertRaises(GrpcTesterError):
            assert_call_fails(self._fail(), status="weird")  # type: ignore[arg-type]

    def test_assert_called_pass(self):
        rec = GrpcCallRecorder()
        rec.record(self._ok())
        assert_called(rec, "X")

    def test_assert_called_fail(self):
        with self.assertRaises(GrpcTesterError):
            assert_called(GrpcCallRecorder(), "X")


if __name__ == "__main__":
    unittest.main()
