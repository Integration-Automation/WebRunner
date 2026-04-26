import json
import tempfile
import unittest
from pathlib import Path

from je_web_runner.utils.trend_dashboard import (
    TrendDashboardError,
    compute_trend,
    render_html,
)
from je_web_runner.utils.trend_dashboard.trend import write_dashboard


def _ledger_with(runs):
    return json.dumps({"runs": runs})


class TestComputeTrend(unittest.TestCase):

    def test_buckets_by_day(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "ledger.json"
            ledger.write_text(_ledger_with([
                {"path": "a", "passed": True, "time": "2026-04-25T10:00:00",
                 "duration_seconds": 5},
                {"path": "b", "passed": False, "time": "2026-04-25T11:00:00",
                 "duration_seconds": 7},
                {"path": "c", "passed": True, "time": "2026-04-26T08:00:00",
                 "duration_seconds": 3},
            ]), encoding="utf-8")
            trend = compute_trend(str(ledger))
            self.assertEqual(len(trend["daily"]), 2)
            day_one = trend["daily"][0]
            self.assertEqual(day_one["total"], 2)
            self.assertEqual(day_one["passed"], 1)
            self.assertAlmostEqual(day_one["pass_rate"], 0.5)
            self.assertAlmostEqual(day_one["avg_duration_seconds"], 6.0)

    def test_missing_ledger_raises(self):
        with self.assertRaises(TrendDashboardError):
            compute_trend("nope.json")

    def test_invalid_json_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "x.json"
            ledger.write_text("not json", encoding="utf-8")
            with self.assertRaises(TrendDashboardError):
                compute_trend(str(ledger))

    def test_missing_runs_key_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "x.json"
            ledger.write_text(json.dumps({"other": []}), encoding="utf-8")
            with self.assertRaises(TrendDashboardError):
                compute_trend(str(ledger))


class TestRender(unittest.TestCase):

    def test_render_includes_title_and_table(self):
        trend = {"daily": [
            {"label": "2026-04-25", "passed": 1, "failed": 0, "total": 1,
             "pass_rate": 1.0, "avg_duration_seconds": 1.5},
        ], "totals": {}}
        text = render_html(trend, title="Demo")
        self.assertIn("Demo", text)
        self.assertIn("2026-04-25", text)
        self.assertIn("100.0%", text)

    def test_render_handles_empty(self):
        text = render_html({"daily": [], "totals": {}})
        self.assertIn("No runs recorded yet", text)

    def test_write_dashboard_creates_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = write_dashboard(
                {"daily": [], "totals": {}},
                str(Path(tmpdir) / "out.html"),
            )
            self.assertTrue(target.is_file())


if __name__ == "__main__":
    unittest.main()
