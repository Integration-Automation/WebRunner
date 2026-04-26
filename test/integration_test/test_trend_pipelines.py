"""
Integration: run_ledger.record_run → trend_dashboard.compute_trend, plus
a11y_trend.aggregate_history fed real axe-shaped runs.

Both produce HTML; we render and confirm dates / pass-rate make it into
the output.
"""
import tempfile
import unittest
from pathlib import Path

from je_web_runner.utils.a11y_trend.trend import (
    aggregate_history,
    render_html as render_a11y_html,
)
from je_web_runner.utils.run_ledger.ledger import record_run
from je_web_runner.utils.trend_dashboard.trend import (
    compute_trend,
    render_html as render_run_html,
)


class TestRunTrendPipeline(unittest.TestCase):

    def test_record_then_compute_then_render(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "ledger.json"
            for path in ["a.json", "b.json", "c.json"]:
                record_run(str(ledger), path, passed=True)
            record_run(str(ledger), "d.json", passed=False)

            trend = compute_trend(str(ledger))
            self.assertEqual(trend["totals"]["total"], 4)
            self.assertEqual(trend["totals"]["passed"], 3)
            self.assertEqual(trend["totals"]["failed"], 1)

            html = render_run_html(trend, title="run trend")
            self.assertIn("Total", html)
            self.assertIn("Passed", html)


class TestA11yTrendPipeline(unittest.TestCase):

    def test_aggregate_then_render(self):
        history = [
            {"timestamp": "2026-04-25T08:00:00",
             "violations": [
                 {"id": "label", "impact": "serious",
                  "nodes": [{"target": ["input.email"]}]},
                 {"id": "color-contrast", "impact": "moderate",
                  "nodes": [{"target": ["html>body>h1"]}]},
             ]},
            {"timestamp": "2026-04-26T08:00:00",
             "violations": [
                 {"id": "label", "impact": "serious",
                  "nodes": [{"target": ["input.email"]}]},
             ]},
        ]
        points = aggregate_history(history)
        self.assertEqual(len(points), 2)
        self.assertEqual(points[0].impacts["serious"], 1)
        self.assertEqual(points[0].impacts["moderate"], 1)
        self.assertEqual(points[1].impacts["serious"], 1)

        html = render_a11y_html(points, title="a11y")
        self.assertIn("a11y", html)
        self.assertIn("2026-04-25", html)
        self.assertIn("2026-04-26", html)


if __name__ == "__main__":
    unittest.main()
