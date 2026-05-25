"""Unit tests for je_web_runner.utils.test_roi_scorer."""
import unittest

from je_web_runner.utils.test_roi_scorer.score import (
    RoiMetrics,
    RoiScorerError,
    Weights,
    removal_candidates,
    score_many,
    score_one,
)


class TestRoiMetricsClass(unittest.TestCase):

    def test_basic(self):
        m = RoiMetrics(name="t", runs=10, real_failures=1)
        self.assertEqual(m.name, "t")

    def test_empty_name(self):
        with self.assertRaises(RoiScorerError):
            RoiMetrics(name="")

    def test_negative_runs(self):
        with self.assertRaises(RoiScorerError):
            RoiMetrics(name="t", runs=-1)

    def test_failures_exceed_runs(self):
        with self.assertRaises(RoiScorerError):
            RoiMetrics(name="t", runs=2, real_failures=5)


class TestRoiScoreOne(unittest.TestCase):

    def test_high_value_test(self):
        m = RoiMetrics(
            name="great", runs=100, real_failures=10,
            duration_seconds=5, unique_lines_covered=300,
            days_since_last_real_failure=1,
        )
        s = score_one(m)
        self.assertGreaterEqual(s.score, 0.7)
        self.assertEqual(s.verdict, "keep")

    def test_remove_candidate(self):
        m = RoiMetrics(
            name="bad", runs=100, real_failures=0, flake_failures=30,
            duration_seconds=120, unique_lines_covered=0,
            days_since_last_real_failure=9999,
        )
        s = score_one(m)
        self.assertEqual(s.verdict, "consider-removing")

    def test_invalid_weights(self):
        with self.assertRaises(RoiScorerError):
            score_one(RoiMetrics(name="x"), Weights(0.5, 0.5, 0.5, 0.5))

    def test_bad_metric(self):
        with self.assertRaises(RoiScorerError):
            score_one("nope")

    def test_components_in_range(self):
        m = RoiMetrics(name="x", runs=10, real_failures=1,
                        days_since_last_real_failure=10)
        s = score_one(m)
        for v in s.components.values():
            self.assertTrue(0 <= v <= 1)


class TestRoiScoreMany(unittest.TestCase):

    def test_sorted_descending(self):
        metrics = [
            RoiMetrics(name="bad", runs=10, real_failures=0,
                        flake_failures=5, duration_seconds=60),
            RoiMetrics(name="good", runs=10, real_failures=5,
                        unique_lines_covered=300,
                        days_since_last_real_failure=0),
        ]
        scores = score_many(metrics)
        self.assertEqual(scores[0].name, "good")

    def test_bad_type(self):
        with self.assertRaises(RoiScorerError):
            score_many("nope")


class TestRemovalCandidates(unittest.TestCase):

    def test_filter(self):
        scores = score_many([
            RoiMetrics(name="bad", runs=10, real_failures=0,
                        flake_failures=5, duration_seconds=60),
            RoiMetrics(name="good", runs=10, real_failures=5,
                        unique_lines_covered=300,
                        days_since_last_real_failure=0),
        ])
        cand = removal_candidates(scores, max_score=0.3)
        self.assertEqual([s.name for s in cand], ["bad"])

    def test_bad_max(self):
        with self.assertRaises(RoiScorerError):
            removal_candidates([], max_score=2)


if __name__ == "__main__":
    unittest.main()
