"""Unit tests for je_web_runner.utils.flag_matrix."""
import unittest

from je_web_runner.utils.flag_matrix.matrix import (
    ComboResult,
    FlagMatrixError,
    FlagSpec,
    build_matrix,
    forbid,
    require,
    smallest_failing_subset,
    summarise_results,
)


class TestFlagSpec(unittest.TestCase):

    def test_rejects_empty_variants(self):
        with self.assertRaises(FlagMatrixError):
            FlagSpec("x", [])

    def test_rejects_duplicate_variants(self):
        with self.assertRaises(FlagMatrixError):
            FlagSpec("x", ["a", "a"])

    def test_rejects_bad_name(self):
        with self.assertRaises(FlagMatrixError):
            FlagSpec("", ["a"])


class TestBuildMatrix(unittest.TestCase):

    def test_cartesian(self):
        m = build_matrix([
            FlagSpec("checkout", ["v1", "v2"]),
            FlagSpec("dark_mode", [True, False]),
        ])
        self.assertEqual(m.total_possible, 4)
        self.assertEqual(len(m), 4)

    def test_constraint_filters(self):
        m = build_matrix(
            [FlagSpec("a", [1, 2]), FlagSpec("b", [True, False])],
            constraints=[forbid((("a", 1), ("b", True)))],
        )
        self.assertEqual(len(m), 3)
        self.assertEqual(m.constrained_out, 1)
        self.assertNotIn({"a": 1, "b": True}, m.combos)

    def test_require_constraint(self):
        m = build_matrix(
            [FlagSpec("a", [1, 2]), FlagSpec("b", [True, False])],
            constraints=[require((("a", 1), ("b", True)))],
        )
        for combo in m:
            if combo["a"] == 1:
                self.assertTrue(combo["b"])

    def test_pinned_always_present(self):
        m = build_matrix(
            [FlagSpec("a", [1, 2]), FlagSpec("b", [True, False])],
            pinned=[{"a": 1, "b": True}, {"a": 2, "b": False}],
            constraints=[forbid((("a", 1), ("b", True)))],
        )
        # Pinned skips the constraint
        self.assertIn({"a": 1, "b": True}, m.combos)
        self.assertEqual(m.pinned_count, 2)

    def test_pinned_dedup(self):
        m = build_matrix(
            [FlagSpec("a", [1, 2])],
            pinned=[{"a": 1}, {"a": 1}],
        )
        self.assertEqual(m.pinned_count, 1)

    def test_pinned_validates_keys(self):
        with self.assertRaises(FlagMatrixError):
            build_matrix(
                [FlagSpec("a", [1, 2])],
                pinned=[{"wrong_key": 1}],
            )

    def test_pinned_validates_value(self):
        with self.assertRaises(FlagMatrixError):
            build_matrix(
                [FlagSpec("a", [1, 2])],
                pinned=[{"a": 99}],
            )

    def test_sample_size_deterministic(self):
        flags = [FlagSpec("a", list(range(5))), FlagSpec("b", list(range(5)))]
        a = build_matrix(flags, sample_size=5, seed=42)
        b = build_matrix(flags, sample_size=5, seed=42)
        self.assertEqual(list(a), list(b))
        self.assertTrue(a.sampled)
        self.assertEqual(len(a), 5)

    def test_sample_keeps_pinned(self):
        flags = [FlagSpec("a", list(range(5))), FlagSpec("b", list(range(5)))]
        m = build_matrix(flags, sample_size=3, pinned=[{"a": 0, "b": 0}], seed=1)
        self.assertIn({"a": 0, "b": 0}, m.combos)
        self.assertLessEqual(len(m), 3)

    def test_constraint_kills_all_raises(self):
        with self.assertRaises(FlagMatrixError):
            build_matrix(
                [FlagSpec("a", [1, 2])],
                constraints=[lambda combo: False],
            )

    def test_bad_constraint_raises(self):
        def boom(_combo):
            raise RuntimeError("nope")
        with self.assertRaises(FlagMatrixError):
            build_matrix([FlagSpec("a", [1])], constraints=[boom])

    def test_no_flags_rejected(self):
        with self.assertRaises(FlagMatrixError):
            build_matrix([])

    def test_duplicate_flag_names_rejected(self):
        with self.assertRaises(FlagMatrixError):
            build_matrix([FlagSpec("a", [1]), FlagSpec("a", [2])])

    def test_bad_sample_size(self):
        with self.assertRaises(FlagMatrixError):
            build_matrix([FlagSpec("a", [1])], sample_size=0)


class TestSummarise(unittest.TestCase):

    def test_counts(self):
        results = [
            ComboResult(combo={"a": 1}, passed=True, duration_seconds=1.0),
            ComboResult(combo={"a": 2}, passed=False, duration_seconds=2.0, error="x"),
            ComboResult(combo={"a": 3}, passed=True, duration_seconds=3.0),
        ]
        report = summarise_results(results)
        self.assertEqual(report.total, 3)
        self.assertEqual(report.passed, 2)
        self.assertEqual(report.failed, 1)
        self.assertEqual(len(report.failures), 1)
        self.assertEqual(report.average_seconds, 2.0)

    def test_rejects_non_combo_result(self):
        with self.assertRaises(FlagMatrixError):
            summarise_results(["bad"])  # type: ignore[list-item]


class TestSmallestFailingSubset(unittest.TestCase):

    def test_single_culprit_flag(self):
        failures = [
            ComboResult(combo={"checkout": "v2", "dark": True}, passed=False),
            ComboResult(combo={"checkout": "v2", "dark": False}, passed=False),
            ComboResult(combo={"checkout": "v2", "exp": "B"}, passed=False),
        ]
        subset = smallest_failing_subset(failures)
        self.assertEqual(subset, ["checkout='v2'"])

    def test_empty(self):
        self.assertEqual(smallest_failing_subset([]), [])

    def test_no_single_explanation(self):
        failures = [
            ComboResult(combo={"a": 1, "b": 1}, passed=False),
            ComboResult(combo={"a": 2, "b": 2}, passed=False),
        ]
        subset = smallest_failing_subset(failures)
        self.assertGreaterEqual(len(subset), 2)


if __name__ == "__main__":
    unittest.main()
