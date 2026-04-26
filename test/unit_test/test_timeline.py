import unittest

from je_web_runner.utils.observability.timeline import (
    build,
    from_console,
    from_responses,
    from_spans,
    merge,
    to_dicts,
)


class TestTimeline(unittest.TestCase):

    def test_spans_emit_start_and_end(self):
        events = from_spans([{"name": "click", "start_ms": 100, "end_ms": 250}])
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].kind, "span.start")
        self.assertEqual(events[1].kind, "span.end")
        self.assertEqual(events[1].payload["duration_ms"], 150.0)

    def test_console_uses_index_when_no_timestamp(self):
        events = from_console([{"type": "log", "text": "a"}, {"type": "error", "text": "b"}])
        self.assertEqual(events[0].timestamp_ms, 0.0)
        self.assertEqual(events[1].timestamp_ms, 1.0)

    def test_responses_label(self):
        events = from_responses([{"url": "/x", "method": "POST", "status": 201}])
        self.assertEqual(events[0].label, "POST 201")

    def test_merge_sorts_by_timestamp(self):
        spans = from_spans([{"name": "s", "start_ms": 50, "end_ms": 60}])
        console = from_console([{"type": "log", "ts": 30, "text": "before"}])
        merged = merge(spans, console)
        self.assertEqual(merged[0].timestamp_ms, 30.0)
        self.assertEqual(merged[1].timestamp_ms, 50.0)

    def test_build_to_dicts(self):
        events = build(
            spans=[{"name": "open", "start_ms": 0, "end_ms": 5}],
            console=[{"type": "log", "ts": 2, "text": "hello"}],
            responses=[{"url": "/", "status": 200, "ts": 4}],
        )
        kinds = [e["kind"] for e in events]
        self.assertEqual(kinds[0], "span.start")
        self.assertIn("console", kinds)
        self.assertIn("response", kinds)


if __name__ == "__main__":
    unittest.main()
