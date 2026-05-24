"""Unit tests for je_web_runner.utils.bug_repro_stability."""
import unittest

from je_web_runner.utils.bug_repro_stability.stability import (
    BugReproStabilityError,
    ReproCategory,
    RunOutcome,
    assert_deterministic,
    assert_min_repro_pct,
    repeat,
    report_markdown,
)


def _always_fails(error="boom"):
    def _probe(_i):
        return RunOutcome(passed=False, error_signature=error, duration_seconds=0.1)
    return _probe


def _always_passes():
    def _probe(_i):
        return RunOutcome(passed=True, duration_seconds=0.1)
    return _probe


def _alternating():
    def _probe(i):
        return RunOutcome(passed=(i % 2 == 0), duration_seconds=0.1)
    return _probe


class TestRepeat(unittest.TestCase):

    def test_deterministic_fail(self):
        report = repeat(_always_fails(), attempts=5)
        self.assertEqual(report.repro_pct, 100.0)
        self.assertEqual(report.category, ReproCategory.DETERMINISTIC)

    def test_non_reproducible(self):
        report = repeat(_always_passes(), attempts=5)
        self.assertEqual(report.repro_pct, 0.0)
        self.assertEqual(report.category, ReproCategory.NON_REPRODUCIBLE)

    def test_flaky(self):
        report = repeat(_alternating(), attempts=4)
        self.assertEqual(report.repro_pct, 50.0)
        self.assertEqual(report.category, ReproCategory.FLAKY)

    def test_streak_tracking(self):
        # passes for 3 then fails for 2
        outcomes = [
            RunOutcome(passed=True), RunOutcome(passed=True),
            RunOutcome(passed=True), RunOutcome(passed=False),
            RunOutcome(passed=False),
        ]
        report = repeat(lambda i: outcomes[i], attempts=5)
        self.assertEqual(report.longest_pass_streak, 3)
        self.assertEqual(report.longest_fail_streak, 2)

    def test_error_signature_grouping(self):
        outcomes = [
            RunOutcome(passed=False, error_signature="ElementNotVisible"),
            RunOutcome(passed=False, error_signature="ElementNotVisible"),
            RunOutcome(passed=False, error_signature="Timeout"),
        ]
        report = repeat(lambda i: outcomes[i], attempts=3)
        self.assertEqual(report.errors["ElementNotVisible"], 2)
        self.assertEqual(report.errors["Timeout"], 1)

    def test_stop_on_first_failure(self):
        outcomes = [
            RunOutcome(passed=True), RunOutcome(passed=False),
            RunOutcome(passed=True),
        ]
        report = repeat(lambda i: outcomes[i], attempts=10,
                        stop_on_first_failure=True)
        self.assertEqual(report.attempts, 2)

    def test_stop_on_first_pass(self):
        outcomes = [
            RunOutcome(passed=False), RunOutcome(passed=True),
        ]
        report = repeat(lambda i: outcomes[i], attempts=10,
                        stop_on_first_pass=True)
        self.assertEqual(report.attempts, 2)

    def test_runner_must_be_callable(self):
        with self.assertRaises(BugReproStabilityError):
            repeat("nope")  # type: ignore[arg-type]

    def test_bad_attempts(self):
        with self.assertRaises(BugReproStabilityError):
            repeat(_always_fails(), attempts=0)

    def test_runner_exception(self):
        def boom(_i):
            raise RuntimeError("crash")
        with self.assertRaises(BugReproStabilityError):
            repeat(boom)

    def test_runner_must_return_outcome(self):
        def bad(_i):
            return "nope"
        with self.assertRaises(BugReproStabilityError):
            repeat(bad)


class TestAssertions(unittest.TestCase):

    def test_assert_deterministic_pass(self):
        assert_deterministic(repeat(_always_fails(), attempts=3))

    def test_assert_deterministic_fail(self):
        with self.assertRaises(BugReproStabilityError):
            assert_deterministic(repeat(_alternating(), attempts=4))

    def test_assert_deterministic_rejects_non_report(self):
        with self.assertRaises(BugReproStabilityError):
            assert_deterministic("nope")  # type: ignore[arg-type]

    def test_assert_min_repro_pass(self):
        assert_min_repro_pct(repeat(_alternating(), attempts=4), minimum=40.0)

    def test_assert_min_repro_fail(self):
        with self.assertRaises(BugReproStabilityError):
            assert_min_repro_pct(repeat(_alternating(), attempts=4), minimum=80.0)

    def test_assert_min_repro_bad_threshold(self):
        with self.assertRaises(BugReproStabilityError):
            assert_min_repro_pct(repeat(_always_fails()), minimum=200.0)


class TestMarkdown(unittest.TestCase):

    def test_renders(self):
        report = repeat(_always_fails("Timeout"), attempts=3)
        md = report_markdown(report)
        self.assertIn("deterministic", md)
        self.assertIn("Timeout", md)

    def test_rejects_non_report(self):
        with self.assertRaises(BugReproStabilityError):
            report_markdown("nope")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
