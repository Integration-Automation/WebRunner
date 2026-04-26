import json
import tempfile
import unittest
from pathlib import Path

from je_web_runner.utils.a11y_trend import (
    A11yTrendError,
    aggregate_history,
    render_html,
)
from je_web_runner.utils.a11y_trend.trend import (
    load_history,
    write_dashboard,
)


def _entry(timestamp, violations):
    return {"timestamp": timestamp, "violations": violations}


def _violation(impact, nodes=1):
    return {
        "id": "fake",
        "impact": impact,
        "nodes": [{"target": ["x"]} for _ in range(nodes)],
    }


class TestAggregateHistory(unittest.TestCase):

    def test_buckets_per_day_and_impact(self):
        history = [
            _entry("2026-04-25T10:00", [_violation("serious"), _violation("moderate")]),
            _entry("2026-04-25T18:00", [_violation("serious", nodes=3)]),
            _entry("2026-04-26T08:00", [_violation("minor")]),
        ]
        points = aggregate_history(history)
        self.assertEqual(len(points), 2)
        first = points[0]
        self.assertEqual(first.label, "2026-04-25")
        self.assertEqual(first.impacts["serious"], 4)
        self.assertEqual(first.impacts["moderate"], 1)
        self.assertEqual(points[1].impacts["minor"], 1)

    def test_unknown_impact_label(self):
        history = [_entry("2026-04-25", [{"id": "x"}])]
        points = aggregate_history(history)
        self.assertEqual(points[0].impacts["unknown"], 1)

    def test_invalid_history(self):
        with self.assertRaises(A11yTrendError):
            aggregate_history(None)
        with self.assertRaises(A11yTrendError):
            aggregate_history(["not a dict"])  # type: ignore[list-item]
        with self.assertRaises(A11yTrendError):
            aggregate_history([{"violations": "not a list"}])


class TestRenderHtml(unittest.TestCase):

    def test_renders_table_and_chart(self):
        history = [
            _entry("2026-04-25", [_violation("serious")]),
        ]
        text = render_html(aggregate_history(history))
        self.assertIn("A11y trend", text)
        self.assertIn("2026-04-25", text)
        self.assertIn("<svg", text)

    def test_empty_points(self):
        text = render_html([])
        self.assertIn("No history yet", text)


class TestWriteDashboard(unittest.TestCase):

    def test_writes_html_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "a11y.html"
            history = [_entry("2026-04-25", [_violation("serious")])]
            path = write_dashboard(history, target)
            self.assertTrue(path.is_file())


class TestLoadHistory(unittest.TestCase):

    def test_loads_list(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "history.json"
            path.write_text(json.dumps([
                _entry("2026-04-25", [_violation("serious")]),
            ]), encoding="utf-8")
            self.assertEqual(len(load_history(path)), 1)

    def test_missing_file_raises(self):
        with self.assertRaises(A11yTrendError):
            load_history("does/not/exist.json")

    def test_invalid_json_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "history.json"
            path.write_text("not json", encoding="utf-8")
            with self.assertRaises(A11yTrendError):
                load_history(path)

    def test_root_must_be_list(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "history.json"
            path.write_text(json.dumps({"not": "list"}), encoding="utf-8")
            with self.assertRaises(A11yTrendError):
                load_history(path)


if __name__ == "__main__":
    unittest.main()
