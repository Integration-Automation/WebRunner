"""Unit tests for je_web_runner.utils.test_cost_estimator."""
import json
import tempfile
import unittest
from pathlib import Path

from je_web_runner.utils.test_cost_estimator.estimator import (
    DEFAULT_RATE_CARDS,
    RateCard,
    RunRow,
    TestCostEstimatorError,
    estimate_markdown,
    estimate_runs,
    load_runs,
    rate_card_index,
)


def _runs(*tuples):
    return [RunRow(test_id=tid, runner=runner, duration_seconds=sec)
            for tid, runner, sec in tuples]


class TestRateCard(unittest.TestCase):

    def test_rejects_negative_rate(self):
        with self.assertRaises(TestCostEstimatorError):
            RateCard(runner="x", usd_per_minute=-1)

    def test_rejects_negative_co2(self):
        with self.assertRaises(TestCostEstimatorError):
            RateCard(runner="x", usd_per_minute=1, grams_co2_per_minute=-1)

    def test_rejects_negative_minimum(self):
        with self.assertRaises(TestCostEstimatorError):
            RateCard(runner="x", usd_per_minute=1, minimum_minutes=-1)


class TestRateCardIndex(unittest.TestCase):

    def test_duplicates_rejected(self):
        with self.assertRaises(TestCostEstimatorError):
            rate_card_index([
                RateCard(runner="a", usd_per_minute=1),
                RateCard(runner="a", usd_per_minute=2),
            ])

    def test_returns_dict(self):
        idx = rate_card_index([RateCard(runner="a", usd_per_minute=1)])
        self.assertIn("a", idx)


class TestRunRow(unittest.TestCase):

    def test_rejects_negative_duration(self):
        with self.assertRaises(TestCostEstimatorError):
            RunRow(test_id="t", runner="local", duration_seconds=-1)


class TestLoadRuns(unittest.TestCase):

    def test_loads_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "l.json"
            p.write_text(json.dumps({"runs": [
                {"test_id": "t1", "runner": "saucelabs", "duration_seconds": 30},
                {"path": "t2", "runner": "local", "duration_seconds": 5},
                {"test_id": "skip_me", "runner": "local"},  # no duration → skip
            ]}), encoding="utf-8")
            runs = load_runs(p)
            self.assertEqual(len(runs), 2)
            self.assertEqual(runs[1].test_id, "t2")

    def test_missing_file(self):
        with self.assertRaises(TestCostEstimatorError):
            load_runs("/no/such/file.json")

    def test_bad_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.json"
            p.write_text("nope", encoding="utf-8")
            with self.assertRaises(TestCostEstimatorError):
                load_runs(p)

    def test_missing_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.json"
            p.write_text(json.dumps({"x": []}), encoding="utf-8")
            with self.assertRaises(TestCostEstimatorError):
                load_runs(p)


class TestEstimate(unittest.TestCase):

    def test_uses_defaults(self):
        runs = _runs(("t1", "saucelabs", 120), ("t2", "saucelabs", 60))
        est = estimate_runs(runs)
        self.assertEqual(est.total_runs, 2)
        # 2 + 1 = 3 minutes × $0.18 = $0.54
        self.assertAlmostEqual(est.total_usd, 0.54, places=2)

    def test_minimum_minutes_applied(self):
        runs = _runs(("t1", "saucelabs", 10))  # 10s = 0.17m, billed as 1m
        est = estimate_runs(runs)
        self.assertEqual(est.total_billed_minutes, 1.0)

    def test_unknown_runner_collected(self):
        runs = _runs(("t1", "mystery_cloud", 60))
        est = estimate_runs(runs)
        self.assertEqual(est.total_runs, 0)
        self.assertIn("mystery_cloud", est.unknown_runners)

    def test_per_test_costs(self):
        runs = _runs(("t1", "saucelabs", 600), ("t1", "saucelabs", 300))
        est = estimate_runs(runs)
        self.assertGreater(est.by_test["t1"], 0)

    def test_by_runner_breakdown(self):
        runs = _runs(("a", "saucelabs", 60), ("b", "browserstack", 60))
        est = estimate_runs(runs)
        self.assertIn("saucelabs", est.by_runner)
        self.assertIn("browserstack", est.by_runner)

    def test_empty_rejected(self):
        with self.assertRaises(TestCostEstimatorError):
            estimate_runs([])

    def test_co2_accumulates(self):
        runs = _runs(("t1", "saucelabs", 60))
        est = estimate_runs(runs)
        self.assertGreater(est.total_grams_co2, 0)


class TestEstimateMarkdown(unittest.TestCase):

    def test_renders(self):
        est = estimate_runs(_runs(("t1", "saucelabs", 600)))
        md = estimate_markdown(est)
        self.assertIn("Test cost estimate", md)
        self.assertIn("saucelabs", md)

    def test_top_tests(self):
        est = estimate_runs(_runs(
            ("expensive", "saucelabs", 1200),
            ("cheap", "saucelabs", 60),
        ))
        md = estimate_markdown(est, top_tests=1)
        self.assertIn("expensive", md)

    def test_zero_top_tests(self):
        est = estimate_runs(_runs(("t1", "saucelabs", 60)))
        md = estimate_markdown(est, top_tests=0)
        self.assertNotIn("costliest", md)

    def test_bad_top_tests(self):
        est = estimate_runs(_runs(("t1", "saucelabs", 60)))
        with self.assertRaises(TestCostEstimatorError):
            estimate_markdown(est, top_tests=-1)

    def test_rejects_non_estimate(self):
        with self.assertRaises(TestCostEstimatorError):
            estimate_markdown("not estimate")  # type: ignore[arg-type]


class TestDefaultCards(unittest.TestCase):

    def test_have_well_known_runners(self):
        names = {c.runner for c in DEFAULT_RATE_CARDS}
        self.assertIn("local", names)
        self.assertIn("saucelabs", names)
        self.assertIn("browserstack", names)


if __name__ == "__main__":
    unittest.main()
