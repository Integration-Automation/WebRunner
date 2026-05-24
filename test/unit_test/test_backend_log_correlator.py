"""Unit tests for je_web_runner.utils.backend_log_correlator."""
import json
import tempfile
import unittest
from pathlib import Path

from je_web_runner.utils.backend_log_correlator.correlator import (
    BackendLogCorrelatorError,
    CorrelatedLog,
    attach_to_failure_bundle,
    correlate,
    fetch_file_log,
    parse_traceparent,
    validate_trace_id,
)

_TRACE = "0af7651916cd43dd8448eb211c80319c"
_HEADER = f"00-{_TRACE}-b7ad6b7169203331-01"


class TestTraceparent(unittest.TestCase):

    def test_parse_valid(self):
        self.assertEqual(parse_traceparent(_HEADER), _TRACE)

    def test_parse_uppercase_normalises(self):
        self.assertEqual(parse_traceparent(_HEADER.upper()), _TRACE)

    def test_parse_invalid(self):
        with self.assertRaises(BackendLogCorrelatorError):
            parse_traceparent("not-a-header")

    def test_parse_empty(self):
        with self.assertRaises(BackendLogCorrelatorError):
            parse_traceparent("")

    def test_validate_trace_id(self):
        self.assertEqual(validate_trace_id(_TRACE), _TRACE)

    def test_validate_bad_trace_id(self):
        with self.assertRaises(BackendLogCorrelatorError):
            validate_trace_id("short")


class TestFileFetcher(unittest.TestCase):

    def _write_log(self, tmpdir, lines):
        path = Path(tmpdir) / "app.log"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def test_json_line_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_log(tmp, [
                json.dumps({"trace_id": _TRACE, "level": "ERROR", "msg": "boom",
                            "service": "checkout"}),
                json.dumps({"trace_id": "x" * 32, "level": "INFO", "msg": "other"}),
            ])
            logs = fetch_file_log(path)(_TRACE)
            self.assertEqual(len(logs), 1)
            self.assertEqual(logs[0].message, "boom")
            self.assertEqual(logs[0].service, "checkout")

    def test_substring_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_log(tmp, [
                f"plain text line with {_TRACE} in it",
                "unrelated line",
            ])
            logs = fetch_file_log(path)(_TRACE)
            self.assertEqual(len(logs), 1)
            self.assertIn(_TRACE, logs[0].message)

    def test_substring_fallback_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_log(tmp, [f"plain text {_TRACE} here"])
            logs = fetch_file_log(path, fallback_to_substring=False)(_TRACE)
            self.assertEqual(logs, [])

    def test_missing_file_raises(self):
        with self.assertRaises(BackendLogCorrelatorError):
            fetch_file_log("/no/such/file.log")


class TestCorrelate(unittest.TestCase):

    def test_accepts_traceparent_header(self):
        captured: list = []

        def fake(trace_id):
            captured.append(trace_id)
            return [CorrelatedLog(timestamp="t", level="INFO", message="hi")]

        result = correlate(_HEADER, [fake])
        self.assertEqual(captured, [_TRACE])
        self.assertEqual(len(result), 1)

    def test_accepts_bare_trace_id(self):
        result = correlate(_TRACE, [lambda _: []])
        self.assertEqual(result, [])

    def test_merges_multiple_fetchers(self):
        a = lambda _: [CorrelatedLog(timestamp="1", level="I", message="a")]
        b = lambda _: [
            CorrelatedLog(timestamp="2", level="I", message="b"),
            CorrelatedLog(timestamp="3", level="I", message="c"),
        ]
        self.assertEqual(len(correlate(_TRACE, [a, b])), 3)

    def test_no_fetchers_raises(self):
        with self.assertRaises(BackendLogCorrelatorError):
            correlate(_TRACE, [])

    def test_swallows_non_correlator_errors(self):
        def boom(_):
            raise RuntimeError("network down")
        good = lambda _: [CorrelatedLog(timestamp="t", level="I", message="ok")]
        result = correlate(_TRACE, [boom, good])
        self.assertEqual(len(result), 1)

    def test_propagates_correlator_errors(self):
        def bad(_):
            raise BackendLogCorrelatorError("explicit failure")
        with self.assertRaises(BackendLogCorrelatorError):
            correlate(_TRACE, [bad])


class TestAttach(unittest.TestCase):

    def test_writes_logs_into_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "fb"
            bundle.mkdir()
            logs = [CorrelatedLog(timestamp="t", level="ERROR", message="x")]
            out = attach_to_failure_bundle(bundle, logs)
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(data[0]["message"], "x")

    def test_bundle_must_exist(self):
        with self.assertRaises(BackendLogCorrelatorError):
            attach_to_failure_bundle("/no/such/bundle", [])


if __name__ == "__main__":
    unittest.main()
