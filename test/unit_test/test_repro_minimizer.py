"""Unit tests for je_web_runner.utils.repro_minimizer."""
import unittest

from je_web_runner.utils.repro_minimizer.minimizer import (
    MinimizationResult,
    ReproMinimizerError,
    assert_minimized,
    minimize,
    report_markdown,
)


def _runner_failing_when_action_present(culprit):
    """Returns runner that fails (returns False) iff `culprit` is in the subset."""
    def _run(subset):
        return culprit not in subset  # True = pass, False = fail
    return _run


class TestMinimize(unittest.TestCase):

    def test_finds_single_culprit(self):
        actions = list(range(20))
        runner = _runner_failing_when_action_present(7)
        result = minimize(actions, runner)
        self.assertIn(7, result.minimized_actions)
        self.assertEqual(result.minimized_size, 1)
        self.assertEqual(result.original_size, 20)

    def test_two_culprits_together(self):
        actions = list(range(30))
        # Fails only when both 5 AND 17 are present
        def runner(subset):
            return not (5 in subset and 17 in subset)
        result = minimize(actions, runner)
        self.assertIn(5, result.minimized_actions)
        self.assertIn(17, result.minimized_actions)
        self.assertLessEqual(result.minimized_size, 5)

    def test_already_minimal(self):
        actions = ["only_action"]
        # ddmin can't go below 1, so it converges immediately
        result = minimize(actions, _runner_failing_when_action_present("only_action"))
        self.assertEqual(result.minimized_actions, ["only_action"])

    def test_passing_input_rejected(self):
        with self.assertRaises(ReproMinimizerError):
            minimize([1, 2, 3], lambda subset: True)

    def test_skip_verify(self):
        # Even if original "passes" by our stub, with verify_failing=False
        # the minimizer just runs the procedure
        result = minimize([1, 2, 3], lambda subset: True, verify_failing=False)
        self.assertGreaterEqual(result.minimized_size, 1)

    def test_runner_must_be_callable(self):
        with self.assertRaises(ReproMinimizerError):
            minimize([1, 2], "not callable")  # type: ignore[arg-type]

    def test_empty_actions(self):
        with self.assertRaises(ReproMinimizerError):
            minimize([], lambda s: False)

    def test_non_list_rejected(self):
        with self.assertRaises(ReproMinimizerError):
            minimize("string", lambda s: False)  # type: ignore[arg-type]

    def test_max_iterations_bound(self):
        with self.assertRaises(ReproMinimizerError):
            minimize([1], lambda s: False, max_iterations=0)

    def test_runner_exception(self):
        def boom(_subset):
            raise RuntimeError("nope")
        with self.assertRaises(ReproMinimizerError):
            minimize([1, 2, 3], boom)

    def test_eval_count_tracked(self):
        result = minimize(list(range(8)),
                          _runner_failing_when_action_present(3))
        self.assertGreater(result.eval_count, 1)

    def test_reduction_pct(self):
        result = MinimizationResult(
            original_size=10, minimized_actions=[1], minimized_size=1,
        )
        self.assertEqual(result.reduction_pct, 90.0)

    def test_reduction_pct_zero_original(self):
        result = MinimizationResult(
            original_size=0, minimized_actions=[], minimized_size=0,
        )
        self.assertEqual(result.reduction_pct, 0.0)


class TestAssertMinimized(unittest.TestCase):

    def test_pass(self):
        assert_minimized(
            MinimizationResult(original_size=10, minimized_actions=[1, 2],
                               minimized_size=2),
            max_remaining=5,
        )

    def test_fail(self):
        with self.assertRaises(ReproMinimizerError):
            assert_minimized(
                MinimizationResult(original_size=10, minimized_actions=list(range(8)),
                                   minimized_size=8),
                max_remaining=5,
            )

    def test_bad_max_remaining(self):
        with self.assertRaises(ReproMinimizerError):
            assert_minimized(
                MinimizationResult(original_size=10, minimized_actions=[],
                                   minimized_size=0),
                max_remaining=-1,
            )

    def test_rejects_non_result(self):
        with self.assertRaises(ReproMinimizerError):
            assert_minimized("nope", max_remaining=1)  # type: ignore[arg-type]


class TestReport(unittest.TestCase):

    def test_renders(self):
        result = MinimizationResult(
            original_size=60, minimized_actions=[1, 2, 3, 4],
            minimized_size=4, iterations=7, eval_count=42,
            duration_seconds=1.23,
        )
        md = report_markdown(result)
        self.assertIn("4 / 60", md)
        self.assertIn("93%", md)
        self.assertIn("7", md)

    def test_rejects_non_result(self):
        with self.assertRaises(ReproMinimizerError):
            report_markdown("nope")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
