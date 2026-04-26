import json
import tempfile
import unittest
from pathlib import Path

from je_web_runner.utils.perf_metrics.budgets import (
    PerfBudgetError,
    assert_within_budget,
    evaluate_metrics,
    load_budgets,
)


class TestLoadBudgets(unittest.TestCase):

    def test_load_from_list(self):
        budgets = load_budgets([
            {"path": "/x", "metrics": {"lcp_ms": 2500}},
        ])
        self.assertEqual(len(budgets), 1)
        self.assertEqual(budgets[0].metrics["lcp_ms"], 2500)

    def test_load_from_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fp = Path(tmpdir) / "b.json"
            fp.write_text(json.dumps([
                {"path_glob": "/products/*", "metrics": {"fcp_ms": 1800}},
            ]), encoding="utf-8")
            budgets = load_budgets(fp)
            self.assertEqual(len(budgets), 1)

    def test_invalid_metrics_object_raises(self):
        with self.assertRaises(PerfBudgetError):
            load_budgets([{"path": "/x", "metrics": "not-an-object"}])

    def test_missing_path_raises(self):
        with self.assertRaises(PerfBudgetError):
            load_budgets([{"metrics": {"lcp_ms": 1000}}])

    def test_root_must_be_list(self):
        with self.assertRaises(PerfBudgetError):
            load_budgets({"path": "/x", "metrics": {"lcp_ms": 1}})


class TestEvaluate(unittest.TestCase):

    def test_no_match_returns_pass(self):
        budgets = load_budgets([{"path": "/x", "metrics": {"lcp_ms": 1000}}])
        result = evaluate_metrics("/y", {"lcp_ms": 9999}, budgets)
        self.assertTrue(result.passed)
        self.assertIsNone(result.matched_rule)

    def test_within_budget_passes(self):
        budgets = load_budgets([{"path": "/x", "metrics": {"lcp_ms": 1000}}])
        result = evaluate_metrics("/x", {"lcp_ms": 800}, budgets)
        self.assertTrue(result.passed)

    def test_breach_detected(self):
        budgets = load_budgets([{"path": "/x", "metrics": {"lcp_ms": 1000}}])
        result = evaluate_metrics("/x", {"lcp_ms": 1500}, budgets)
        self.assertFalse(result.passed)
        self.assertEqual(result.breaches[0]["metric"], "lcp_ms")

    def test_missing_metric_reported(self):
        budgets = load_budgets([{"path": "/x", "metrics": {"lcp_ms": 1000}}])
        result = evaluate_metrics("/x", {}, budgets)
        self.assertFalse(result.passed)
        self.assertEqual(result.breaches[0]["reason"], "metric missing")

    def test_glob_match(self):
        budgets = load_budgets([
            {"path_glob": "/products/*", "metrics": {"cls": 0.1}},
        ])
        result = evaluate_metrics("/products/42", {"cls": 0.05}, budgets)
        self.assertTrue(result.passed)

    def test_assert_raises(self):
        budgets = load_budgets([{"path": "/x", "metrics": {"lcp_ms": 1000}}])
        result = evaluate_metrics("/x", {"lcp_ms": 9999}, budgets)
        with self.assertRaises(PerfBudgetError):
            assert_within_budget(result)


if __name__ == "__main__":
    unittest.main()
