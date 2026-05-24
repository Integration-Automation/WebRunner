"""Unit tests for je_web_runner.utils.pr_risk_score."""
import unittest

from je_web_runner.utils.pr_risk_score.scorer import (
    PrRiskScoreError,
    PrSignals,
    RiskReport,
    RiskWeights,
    aggregate_signals,
    report_markdown,
    score_pr,
)


class TestPrSignals(unittest.TestCase):

    def test_defaults_safe(self):
        sig = PrSignals()
        report = score_pr(sig)
        self.assertEqual(report.score, 0.0)
        self.assertEqual(report.level, "low")

    def test_negative_rejected(self):
        with self.assertRaises(PrRiskScoreError):
            PrSignals(flaky_tests_touched=-1)

    def test_bad_avg_flake_rejected(self):
        with self.assertRaises(PrRiskScoreError):
            PrSignals(avg_flake_score=1.5)


class TestScore(unittest.TestCase):

    def test_clean_pr_low(self):
        sig = PrSignals(total_tests_touched=10, lines_added=100, lines_covered=100,
                        repo_modules=50, total_locators_touched=20)
        report = score_pr(sig)
        self.assertLess(report.score, 25)
        self.assertEqual(report.level, "low")

    def test_flaky_pr_higher(self):
        clean = score_pr(PrSignals(
            total_tests_touched=10, lines_added=100, lines_covered=100,
        ))
        flaky = score_pr(PrSignals(
            total_tests_touched=10, flaky_tests_touched=8, avg_flake_score=0.7,
            lines_added=100, lines_covered=100,
        ))
        self.assertGreater(flaky.score, clean.score)
        self.assertTrue(any("flake" in r for r in flaky.reasons))

    def test_critical_pr_flagged(self):
        sig = PrSignals(
            total_tests_touched=5, flaky_tests_touched=5, avg_flake_score=1.0,
            impacted_modules=20, repo_modules=20, impacted_critical_paths=4,
            fragile_locators_touched=10, total_locators_touched=10,
            lines_added=100, lines_covered=0,
            migration_files_changed=2, security_files_changed=2,
        )
        report = score_pr(sig)
        self.assertGreaterEqual(report.score, 75.0)
        self.assertEqual(report.level, "critical")
        self.assertTrue(report.is_blocking())

    def test_score_bounded(self):
        sig = PrSignals(
            total_tests_touched=1, flaky_tests_touched=1, avg_flake_score=1.0,
            impacted_modules=10, repo_modules=10, impacted_critical_paths=20,
            fragile_locators_touched=5, total_locators_touched=5,
            lines_added=10, lines_covered=0,
            migration_files_changed=10, security_files_changed=10,
        )
        report = score_pr(sig)
        self.assertLessEqual(report.score, 100.0)
        self.assertGreaterEqual(report.score, 0.0)

    def test_contributions_sum_recorded(self):
        sig = PrSignals(
            total_tests_touched=2, flaky_tests_touched=1, avg_flake_score=0.5,
            lines_added=10, lines_covered=5,
        )
        report = score_pr(sig)
        self.assertIn("flake", report.contributions)
        self.assertIn("coverage_gap", report.contributions)

    def test_zero_weights_rejected(self):
        weights = RiskWeights(
            flake=0, blast_radius=0, critical_path=0,
            locator_fragility=0, coverage_gap=0, migration=0, security=0,
        )
        with self.assertRaises(PrRiskScoreError):
            score_pr(PrSignals(), weights)

    def test_invalid_signals_type(self):
        with self.assertRaises(PrRiskScoreError):
            score_pr("not signals")  # type: ignore[arg-type]

    def test_coverage_gap_zero_when_no_added(self):
        sig = PrSignals(lines_added=0, lines_covered=0)
        self.assertEqual(score_pr(sig).contributions["coverage_gap"], 0.0)

    def test_custom_weights_change_score(self):
        sig = PrSignals(
            lines_added=10, lines_covered=0,
            total_tests_touched=10, flaky_tests_touched=10, avg_flake_score=1.0,
        )
        low_flake_weight = score_pr(sig, RiskWeights(flake=0.1))
        high_flake_weight = score_pr(sig, RiskWeights(flake=10.0))
        self.assertGreater(high_flake_weight.score, low_flake_weight.score)


class TestAggregateSignals(unittest.TestCase):

    def test_sums_per_file(self):
        per_file = [
            {"flaky_tests_touched": 1, "total_tests_touched": 3, "avg_flake_score": 0.5,
             "repo_modules": 50, "lines_added": 100, "lines_covered": 80},
            {"flaky_tests_touched": 2, "total_tests_touched": 4, "avg_flake_score": 0.7,
             "repo_modules": 50, "lines_added": 50, "lines_covered": 40},
        ]
        sig = aggregate_signals(per_file)
        self.assertEqual(sig.flaky_tests_touched, 3)
        self.assertEqual(sig.total_tests_touched, 7)
        self.assertEqual(sig.lines_added, 150)
        self.assertEqual(sig.repo_modules, 50)
        self.assertAlmostEqual(sig.avg_flake_score, 0.6, places=4)

    def test_ignores_non_dict_entries(self):
        sig = aggregate_signals(["bad", None, {}])  # type: ignore[list-item]
        self.assertEqual(sig.flaky_tests_touched, 0)

    def test_ignores_unknown_keys(self):
        sig = aggregate_signals([{"weird_key": 99, "lines_added": 5}])
        self.assertEqual(sig.lines_added, 5)


class TestReportMarkdown(unittest.TestCase):

    def test_with_reasons(self):
        report = RiskReport(score=80.0, level="critical", reasons=["flake: 50% × 2.0"])
        md = report_markdown(report)
        self.assertIn("80.0", md)
        self.assertIn("critical", md)
        self.assertIn("flake", md)

    def test_no_reasons(self):
        md = report_markdown(RiskReport(score=0.0, level="low"))
        self.assertIn("No risk signals", md)


if __name__ == "__main__":
    unittest.main()
