import tempfile
import unittest
from unittest.mock import MagicMock

from je_web_runner.utils.trace_recorder import (
    TraceRecorder,
    TraceRecorderError,
)


class TestTraceRecorder(unittest.TestCase):

    def test_start_stop_writes_zip_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            context = MagicMock()
            recorder = TraceRecorder(output_dir=tmpdir)
            recorder.start(context, "demo")
            target = recorder.stop(context)
            self.assertTrue(target.endswith("demo.zip"))
            context.tracing.start.assert_called_once()
            context.tracing.stop.assert_called_once()
            self.assertEqual(recorder.written(), [target])

    def test_double_start_raises(self):
        context = MagicMock()
        recorder = TraceRecorder()
        recorder.start(context, "a")
        with self.assertRaises(TraceRecorderError):
            recorder.start(context, "b")

    def test_stop_without_start_raises(self):
        recorder = TraceRecorder()
        with self.assertRaises(TraceRecorderError):
            recorder.stop(MagicMock())

    def test_unsupported_context_raises(self):
        recorder = TraceRecorder()
        with self.assertRaises(TraceRecorderError):
            recorder.start(object(), "x")

    def test_empty_name_rejected(self):
        recorder = TraceRecorder()
        with self.assertRaises(TraceRecorderError):
            recorder.start(MagicMock(), "")

    def test_start_propagates_failure(self):
        recorder = TraceRecorder()
        context = MagicMock()
        context.tracing.start.side_effect = RuntimeError("boom")
        with self.assertRaises(TraceRecorderError):
            recorder.start(context, "x")


if __name__ == "__main__":
    unittest.main()
