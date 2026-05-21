"""
CDP tracing 模組的 mock-based 測試。
透過 mock CDPEventListener 模擬 ``Tracing.dataCollected`` / ``Tracing.tracingComplete``。
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from je_web_runner.utils.cdp.event_loop import CDPEventLoopError
from je_web_runner.utils.cdp.tracing import TracingError, record_trace


def _make_fake_listener(trace_events, complete=True):
    """建一個 fake CDPEventListener：呼叫 send('Tracing.end') 時觸發收到的事件。"""
    listener = MagicMock()
    handlers: dict = {}

    def fake_on(method, callback):
        handlers[method] = callback

    def fake_send(method, params=None, timeout=5.0):
        if method == "Tracing.end":
            data_handler = handlers.get("Tracing.dataCollected")
            if data_handler is not None:
                data_handler({"value": trace_events})
            if complete:
                complete_handler = handlers.get("Tracing.tracingComplete")
                if complete_handler is not None:
                    complete_handler({})
        return {}

    listener.on.side_effect = fake_on
    listener.send.side_effect = fake_send
    listener.__enter__ = MagicMock(return_value=listener)
    listener.__exit__ = MagicMock(return_value=None)
    return listener, handlers


class TestRecordTrace(unittest.TestCase):

    def test_happy_path_writes_events(self):
        events = [{"name": "a"}, {"name": "b"}]
        fake_listener, _ = _make_fake_listener(events)
        with patch(
            "je_web_runner.utils.cdp.tracing.CDPEventListener.from_driver",
            return_value=fake_listener,
        ):
            with tempfile.TemporaryDirectory() as tmpdir:
                path = os.path.join(tmpdir, "trace.json")
                returned = record_trace(MagicMock(), path)
                self.assertEqual(returned, path)
                with open(path, "r", encoding="utf-8") as fh:
                    self.assertEqual(json.load(fh), events)
        # Tracing.start / Tracing.end 都應送出
        sent_methods = [c.args[0] for c in fake_listener.send.call_args_list]
        self.assertIn("Tracing.start", sent_methods)
        self.assertIn("Tracing.end", sent_methods)

    def test_passes_categories_in_start(self):
        fake_listener, _ = _make_fake_listener([])
        with patch(
            "je_web_runner.utils.cdp.tracing.CDPEventListener.from_driver",
            return_value=fake_listener,
        ):
            with tempfile.TemporaryDirectory() as tmpdir:
                record_trace(
                    MagicMock(),
                    os.path.join(tmpdir, "trace.json"),
                    categories=["devtools.timeline", "loading"],
                )
        start_call = next(
            c for c in fake_listener.send.call_args_list if c.args[0] == "Tracing.start"
        )
        params = start_call.args[1]
        self.assertEqual(params["categories"], "devtools.timeline,loading")
        self.assertEqual(params["transferMode"], "ReportEvents")

    def test_no_complete_event_times_out(self):
        fake_listener, _ = _make_fake_listener([{"x": 1}], complete=False)
        with patch(
            "je_web_runner.utils.cdp.tracing.CDPEventListener.from_driver",
            return_value=fake_listener,
        ):
            with tempfile.TemporaryDirectory() as tmpdir:
                with self.assertRaises(TracingError):
                    record_trace(
                        MagicMock(),
                        os.path.join(tmpdir, "trace.json"),
                        completion_timeout=0.1,
                    )

    def test_event_loop_error_wrapped_as_tracing_error(self):
        with patch(
            "je_web_runner.utils.cdp.tracing.CDPEventListener.from_driver",
            side_effect=CDPEventLoopError("ws-client missing"),
        ):
            with tempfile.TemporaryDirectory() as tmpdir:
                with self.assertRaises(TracingError):
                    record_trace(MagicMock(), os.path.join(tmpdir, "trace.json"))

    def test_duration_sleeps_between_start_and_end(self):
        fake_listener, _ = _make_fake_listener([{"x": 1}])
        with patch(
            "je_web_runner.utils.cdp.tracing.CDPEventListener.from_driver",
            return_value=fake_listener,
        ), patch("je_web_runner.utils.cdp.tracing.time.sleep") as sleep_mock:
            with tempfile.TemporaryDirectory() as tmpdir:
                record_trace(
                    MagicMock(),
                    os.path.join(tmpdir, "trace.json"),
                    duration=2.5,
                )
        sleep_mock.assert_called_once_with(2.5)


if __name__ == "__main__":
    unittest.main()
