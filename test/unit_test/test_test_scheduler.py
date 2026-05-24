"""Unit tests for je_web_runner.utils.test_scheduler."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from je_web_runner.utils.test_scheduler.scheduler import (
    Schedule,
    TestCandidate,
    TestSchedulerError,
    build_candidates_from_ledger,
    render_schedule_markdown,
    schedule_tests,
    value_density,
    value_of,
)


def _iso(dt):
    return dt.replace(tzinfo=timezone.utc).isoformat(timespec="seconds")


class TestCandidateValidation(unittest.TestCase):

    def test_empty_id_raises(self):
        with self.assertRaises(TestSchedulerError):
            TestCandidate(test_id="", duration_seconds=1)

    def test_zero_duration_raises(self):
        with self.assertRaises(TestSchedulerError):
            TestCandidate(test_id="t", duration_seconds=0)

    def test_fail_rate_out_of_range(self):
        with self.assertRaises(TestSchedulerError):
            TestCandidate(test_id="t", duration_seconds=1, fail_rate=1.5)

    def test_impact_score_out_of_range(self):
        with self.assertRaises(TestSchedulerError):
            TestCandidate(test_id="t", duration_seconds=1, impact_score=-0.1)


class TestValueModel(unittest.TestCase):

    def test_value_components(self):
        c = TestCandidate(
            test_id="t", duration_seconds=10,
            fail_rate=0.5, impact_score=1.0,
            last_run_age_hours=48, manual_priority=1.0,
        )
        # Expected breakdown: 0.5 fail-rate term + 1.5 impact term + 2.0
        # staleness term + 2.0 manual-priority term equals 6.0 overall.
        self.assertAlmostEqual(value_of(c), 6.0)
        self.assertAlmostEqual(value_density(c), 0.6)


class TestScheduleTests(unittest.TestCase):

    def test_picks_highest_density_first(self):
        candidates = [
            TestCandidate(test_id="slow_low", duration_seconds=100, fail_rate=0.1),
            TestCandidate(test_id="fast_high", duration_seconds=5, fail_rate=0.9),
            TestCandidate(test_id="medium", duration_seconds=20, fail_rate=0.5),
        ]
        sched = schedule_tests(candidates, time_budget_seconds=30)
        self.assertEqual(sched.selected[0], "fast_high")
        self.assertIn("medium", sched.selected)
        self.assertNotIn("slow_low", sched.selected)

    def test_respects_time_budget(self):
        candidates = [
            TestCandidate(test_id="a", duration_seconds=10, fail_rate=0.5),
            TestCandidate(test_id="b", duration_seconds=10, fail_rate=0.5),
            TestCandidate(test_id="c", duration_seconds=10, fail_rate=0.5),
        ]
        sched = schedule_tests(candidates, time_budget_seconds=25)
        # 2 fit, 1 doesn't
        self.assertEqual(len(sched.selected), 2)
        self.assertGreaterEqual(sched.leftover_seconds, 0)

    def test_cloud_quota_limits(self):
        candidates = [
            TestCandidate(test_id="cloud_a", duration_seconds=10,
                          fail_rate=0.9, needs_cloud_session=True),
            TestCandidate(test_id="cloud_b", duration_seconds=10,
                          fail_rate=0.9, needs_cloud_session=True),
            TestCandidate(test_id="local", duration_seconds=10,
                          fail_rate=0.8, needs_cloud_session=False),
        ]
        sched = schedule_tests(
            candidates, time_budget_seconds=100, cloud_slot_budget=1,
        )
        cloud_in_selected = [t for t in sched.selected if t.startswith("cloud_")]
        self.assertEqual(len(cloud_in_selected), 1)
        self.assertIn("local", sched.selected)
        self.assertEqual(sched.leftover_cloud_slots, 0)

    def test_pinned_tests_always_included(self):
        candidates = [
            TestCandidate(test_id="pinned", duration_seconds=20, fail_rate=0.0),
            TestCandidate(test_id="hot", duration_seconds=5, fail_rate=0.9),
        ]
        sched = schedule_tests(
            candidates, time_budget_seconds=30,
            pinned_test_ids=["pinned"],
        )
        self.assertEqual(sched.selected[0], "pinned")
        self.assertIn("hot", sched.selected)

    def test_pinned_overrun_raises(self):
        candidates = [
            TestCandidate(test_id="huge", duration_seconds=1000),
        ]
        with self.assertRaises(TestSchedulerError):
            schedule_tests(
                candidates, time_budget_seconds=10,
                pinned_test_ids=["huge"],
            )

    def test_pinned_unknown_id_raises(self):
        candidates = [TestCandidate(test_id="a", duration_seconds=1)]
        with self.assertRaises(TestSchedulerError):
            schedule_tests(
                candidates, time_budget_seconds=100,
                pinned_test_ids=["ghost"],
            )

    def test_invalid_budget_raises(self):
        with self.assertRaises(TestSchedulerError):
            schedule_tests([], time_budget_seconds=0)
        with self.assertRaises(TestSchedulerError):
            schedule_tests([], time_budget_seconds=100, cloud_slot_budget=-1)

    def test_empty_candidates_returns_empty_schedule(self):
        sched = schedule_tests([], time_budget_seconds=100)
        self.assertEqual(sched.selected, [])
        self.assertEqual(sched.skipped, [])

    def test_cloud_unlimited(self):
        candidates = [
            TestCandidate(test_id="x", duration_seconds=1,
                          fail_rate=0.5, needs_cloud_session=True),
        ]
        sched = schedule_tests(candidates, time_budget_seconds=10)
        # cloud_slot_budget is None → no constraint
        self.assertIn("x", sched.selected)
        self.assertEqual(sched.leftover_cloud_slots, -1)  # sentinel


class TestBuildCandidatesFromLedger(unittest.TestCase):

    def test_builds_from_runs(self):
        now = datetime.now(timezone.utc)
        runs = [
            {"path": "a.json", "passed": True,
             "duration_seconds": 12, "time": _iso(now)},
            {"path": "a.json", "passed": False,
             "duration_seconds": 14, "time": _iso(now)},
            {"path": "b.json", "passed": True,
             "duration_seconds": 30, "time": _iso(now - timedelta(hours=12))},
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "l.json"
            path.write_text(json.dumps({"runs": runs}), encoding="utf-8")
            cands = build_candidates_from_ledger(path)
            by_id = {c.test_id: c for c in cands}
            self.assertEqual(by_id["a.json"].fail_rate, 0.5)
            self.assertAlmostEqual(by_id["a.json"].duration_seconds, 13.0)
            self.assertGreater(by_id["b.json"].last_run_age_hours, 10)

    def test_missing_ledger_returns_empty(self):
        cands = build_candidates_from_ledger("/no/such.json")
        self.assertEqual(cands, [])

    def test_malformed_ledger_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "l.json"
            path.write_text("{}", encoding="utf-8")
            with self.assertRaises(TestSchedulerError):
                build_candidates_from_ledger(path)

    def test_default_duration_when_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "l.json"
            path.write_text(json.dumps({"runs": [
                {"path": "x.json", "passed": True},
            ]}), encoding="utf-8")
            cands = build_candidates_from_ledger(path, default_duration_seconds=45)
            self.assertEqual(cands[0].duration_seconds, 45)

    def test_cloud_set_flags_test(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "l.json"
            path.write_text(json.dumps({"runs": [
                {"path": "x.json", "passed": True, "duration_seconds": 10},
            ]}), encoding="utf-8")
            cands = build_candidates_from_ledger(path, cloud_tests=["x.json"])
            self.assertTrue(cands[0].needs_cloud_session)


class TestRendering(unittest.TestCase):

    def test_markdown_lists_selected_and_skipped(self):
        sched = Schedule(
            selected=["a", "b"], skipped=["c"],
            total_seconds=20, total_cloud_slots=1,
            leftover_seconds=10, leftover_cloud_slots=0,
            value_recovered=3.5,
        )
        md = render_schedule_markdown(sched)
        self.assertIn("Test schedule", md)
        self.assertIn("Selected:** 2", md)
        self.assertIn("`a`", md)
        self.assertIn("`c`", md)


if __name__ == "__main__":
    unittest.main()
