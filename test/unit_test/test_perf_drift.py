import unittest

from je_web_runner.utils.perf_drift import (
    PerfDriftError,
    compute_drift,
    detect_drift,
)
from je_web_runner.utils.perf_drift.drift import (
    assert_no_regression,
    percentile,
)


class TestPercentile(unittest.TestCase):

    def test_p95_simple(self):
        # 0..99 -> P95 = 94.05 with linear interpolation across 100 elements
        values = list(range(100))
        self.assertAlmostEqual(percentile(values, 95), 94.05)

    def test_empty_raises(self):
        with self.assertRaises(PerfDriftError):
            percentile([], 95)

    def test_invalid_pct(self):
        with self.assertRaises(PerfDriftError):
            percentile([1, 2, 3], 120)

    def test_single_value(self):
        self.assertEqual(percentile([42], 95), 42.0)


class TestComputeDrift(unittest.TestCase):

    def test_regression_flagged(self):
        # baseline ~ 100ms, recent ~ 200ms -> 100% increase, way past 10%
        samples = [100] * 20 + [200] * 5
        result = compute_drift(samples, baseline_window=20, recent_window=5)
        self.assertTrue(result.drifted)
        self.assertEqual(result.direction, "regressed")

    def test_improvement_does_not_regress(self):
        samples = [100] * 20 + [50] * 5
        result = compute_drift(samples, baseline_window=20, recent_window=5)
        self.assertEqual(result.direction, "improved")

    def test_higher_is_better(self):
        # frame-rate scenario: drop is the regression
        samples = [60] * 20 + [50] * 5
        result = compute_drift(
            samples, baseline_window=20, recent_window=5, higher_is_better=True,
        )
        self.assertEqual(result.direction, "regressed")

    def test_within_tolerance(self):
        samples = [100, 100, 100, 105, 100, 100, 100, 100, 100, 100,
                   100, 105, 100, 100, 100, 100, 105, 100, 100, 100,
                   100, 105, 100, 100, 100]
        result = compute_drift(samples, baseline_window=20, recent_window=5,
                               tolerance=0.1)
        self.assertFalse(result.drifted)
        self.assertEqual(result.direction, "stable")

    def test_too_few_samples(self):
        with self.assertRaises(PerfDriftError):
            compute_drift([1, 2, 3], baseline_window=10, recent_window=5)

    def test_invalid_windows(self):
        with self.assertRaises(PerfDriftError):
            compute_drift([1, 2, 3], baseline_window=0, recent_window=1)

    def test_invalid_samples_type(self):
        with self.assertRaises(PerfDriftError):
            compute_drift("not-a-list", baseline_window=1, recent_window=1)  # type: ignore[arg-type]


class TestDetectDrift(unittest.TestCase):

    def test_aggregates_metrics(self):
        metrics = {
            "lcp_ms": [1000] * 20 + [2000] * 5,
            "cls": [0.1] * 20 + [0.1] * 5,
        }
        report = detect_drift(metrics, baseline_window=20, recent_window=5)
        regressions = report.regressions
        self.assertEqual(len(regressions), 1)
        self.assertEqual(regressions[0].metric, "lcp_ms")

    def test_assert_no_regression_passes(self):
        metrics = {
            "lcp_ms": [1000] * 20 + [1000] * 5,
        }
        report = detect_drift(metrics, baseline_window=20, recent_window=5)
        assert_no_regression(report)

    def test_assert_no_regression_raises(self):
        metrics = {
            "lcp_ms": [1000] * 20 + [2000] * 5,
        }
        report = detect_drift(metrics, baseline_window=20, recent_window=5)
        with self.assertRaises(PerfDriftError):
            assert_no_regression(report)

    def test_allow_metrics_skips(self):
        metrics = {
            "lcp_ms": [1000] * 20 + [2000] * 5,
        }
        report = detect_drift(metrics, baseline_window=20, recent_window=5)
        assert_no_regression(report, allow_metrics=["lcp_ms"])

    def test_invalid_metrics_input(self):
        with self.assertRaises(PerfDriftError):
            detect_drift({})


if __name__ == "__main__":
    unittest.main()
