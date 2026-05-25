"""Unit tests for je_web_runner.utils.lighthouse_regression."""
import unittest

from je_web_runner.utils.lighthouse_regression.regression import (
    LighthouseRegressionError,
    LighthouseSnapshot,
    ScoreDelta,
    RegressionReport,
    assert_metric_within,
    assert_no_score_regression,
    diff,
    parse_report,
)


REPORT = {
    "categories": {
        "performance": {"score": 0.92},
        "accessibility": {"score": 1.0},
        "best-practices": {"score": 0.85},
        "seo": {"score": 0.9},
    },
    "audits": {
        "largest-contentful-paint": {"numericValue": 2400},
        "cumulative-layout-shift": {"numericValue": 0.05},
        "total-blocking-time": {"numericValue": 150},
    },
}


class TestParse(unittest.TestCase):

    def test_basic(self):
        snap = parse_report(REPORT)
        self.assertEqual(snap.scores["performance"], 92)
        self.assertEqual(snap.metrics["largest-contentful-paint"], 2400)

    def test_bad(self):
        with self.assertRaises(LighthouseRegressionError):
            parse_report("nope")

    def test_bad_categories(self):
        with self.assertRaises(LighthouseRegressionError):
            parse_report({"categories": "nope"})

    def test_skip_null_score(self):
        snap = parse_report({"categories": {"performance": {"score": None}}})
        self.assertNotIn("performance", snap.scores)

    def test_bad_score_value(self):
        with self.assertRaises(LighthouseRegressionError):
            parse_report({"categories": {"performance": {"score": "x"}}})


class TestDiff(unittest.TestCase):

    def test_change(self):
        baseline = LighthouseSnapshot(scores={"performance": 95})
        head = LighthouseSnapshot(scores={"performance": 80})
        report = diff(baseline, head)
        self.assertEqual(report.score_changes[0].delta, -15)

    def test_metric_change(self):
        baseline = LighthouseSnapshot(metrics={"largest-contentful-paint": 2000})
        head = LighthouseSnapshot(metrics={"largest-contentful-paint": 3500})
        report = diff(baseline, head)
        self.assertEqual(report.metric_changes[0].delta, 1500)


class TestRegression(unittest.TestCase):

    def test_pass(self):
        assert_no_score_regression(RegressionReport(score_changes=[
            ScoreDelta(category="performance", baseline=90, head=88),
        ]))

    def test_fail(self):
        with self.assertRaises(LighthouseRegressionError):
            assert_no_score_regression(RegressionReport(score_changes=[
                ScoreDelta(category="performance", baseline=90, head=80),
            ]))

    def test_bad_threshold(self):
        with self.assertRaises(LighthouseRegressionError):
            assert_no_score_regression(RegressionReport(), threshold_points=0)


class TestMetricWithin(unittest.TestCase):

    def test_pass(self):
        assert_metric_within(
            parse_report(REPORT),
            metric="largest-contentful-paint", max_value=3000,
        )

    def test_fail(self):
        with self.assertRaises(LighthouseRegressionError):
            assert_metric_within(
                parse_report(REPORT),
                metric="largest-contentful-paint", max_value=1000,
            )

    def test_bad_metric(self):
        with self.assertRaises(LighthouseRegressionError):
            assert_metric_within(LighthouseSnapshot(),
                                 metric="weird", max_value=1)

    def test_missing(self):
        with self.assertRaises(LighthouseRegressionError):
            assert_metric_within(LighthouseSnapshot(),
                                 metric="largest-contentful-paint",
                                 max_value=1)


if __name__ == "__main__":
    unittest.main()
