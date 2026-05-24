"""Unit tests for je_web_runner.utils.sla_tracker."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from je_web_runner.utils.sla_tracker.tracker import (
    BucketResult,
    SlaReport,
    SlaTarget,
    SlaTrackerError,
    SuiteRun,
    assert_meets_sla,
    compute_sla,
    load_runs,
    report_markdown,
)


_BASE = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)


def _run(suite="checkout", days_offset=0, duration=300, passed=True):
    return SuiteRun(
        suite=suite,
        started_at=_BASE + timedelta(days=days_offset),
        duration_seconds=duration,
        passed=passed,
    )


class TestSuiteRun(unittest.TestCase):

    def test_rejects_empty_suite(self):
        with self.assertRaises(SlaTrackerError):
            SuiteRun(suite="", started_at=_BASE, duration_seconds=0,
                     passed=True)

    def test_rejects_naive_datetime(self):
        with self.assertRaises(SlaTrackerError):
            SuiteRun(suite="x", started_at=datetime(2026, 1, 1),
                     duration_seconds=0, passed=True)

    def test_rejects_negative_duration(self):
        with self.assertRaises(SlaTrackerError):
            SuiteRun(suite="x", started_at=_BASE, duration_seconds=-1,
                     passed=True)


class TestSlaTarget(unittest.TestCase):

    def test_bad_duration(self):
        with self.assertRaises(SlaTrackerError):
            SlaTarget(max_duration_seconds=0, target_pass_pct=95)

    def test_bad_pct(self):
        with self.assertRaises(SlaTrackerError):
            SlaTarget(max_duration_seconds=600, target_pass_pct=0)
        with self.assertRaises(SlaTrackerError):
            SlaTarget(max_duration_seconds=600, target_pass_pct=150)


class TestComputeSla(unittest.TestCase):

    def test_all_met(self):
        runs = [_run(duration=300) for _ in range(5)]
        target = SlaTarget(max_duration_seconds=600, target_pass_pct=95)
        report = compute_sla(runs, target)
        self.assertEqual(report.overall_pct, 100.0)
        self.assertTrue(report.passed())

    def test_partial_met(self):
        runs = [
            _run(duration=300),
            _run(duration=900),  # over budget
        ]
        report = compute_sla(runs, SlaTarget(600, 95))
        self.assertEqual(report.overall_pct, 50.0)
        self.assertFalse(report.passed())

    def test_week_bucketing(self):
        runs = [
            _run(days_offset=0),
            _run(days_offset=10),  # different ISO week
        ]
        report = compute_sla(runs, SlaTarget(600, 95))
        self.assertEqual(len(report.buckets), 2)

    def test_day_bucketing(self):
        runs = [
            _run(days_offset=0),
            _run(days_offset=1),
        ]
        report = compute_sla(runs, SlaTarget(600, 95), bucket="day")
        self.assertEqual(len(report.buckets), 2)

    def test_suite_filter(self):
        runs = [
            _run(suite="checkout"),
            _run(suite="profile"),
        ]
        report = compute_sla(runs, SlaTarget(600, 95), suite="checkout")
        self.assertEqual(report.overall_runs, 1)

    def test_bad_bucket(self):
        with self.assertRaises(SlaTrackerError):
            compute_sla([], SlaTarget(600, 95), bucket="hour")

    def test_rejects_non_run(self):
        with self.assertRaises(SlaTrackerError):
            compute_sla(["nope"], SlaTarget(600, 95))  # type: ignore[list-item]

    def test_empty_runs(self):
        report = compute_sla([], SlaTarget(600, 95))
        self.assertEqual(report.overall_runs, 0)
        self.assertEqual(report.overall_pct, 0.0)


class TestLoadRuns(unittest.TestCase):

    def test_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "l.json"
            path.write_text(json.dumps({"runs": [
                {"suite": "x", "time": "2026-05-01T12:00:00Z",
                 "duration_seconds": 100, "passed": True},
                {"path": "y", "time": "2026-05-02T12:00:00Z",
                 "duration_seconds": 200},
                {"suite": "skipme", "time": "bad timestamp",
                 "duration_seconds": 100},
                {"suite": "skip", "time": "2026-05-01T12:00:00Z"},  # no duration
            ]}), encoding="utf-8")
            runs = load_runs(path)
            self.assertEqual(len(runs), 2)
            self.assertEqual(runs[1].suite, "y")

    def test_missing(self):
        with self.assertRaises(SlaTrackerError):
            load_runs("/no/such/file.json")

    def test_bad_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.json"
            p.write_text("nope", encoding="utf-8")
            with self.assertRaises(SlaTrackerError):
                load_runs(p)

    def test_missing_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.json"
            p.write_text(json.dumps({"x": []}), encoding="utf-8")
            with self.assertRaises(SlaTrackerError):
                load_runs(p)


class TestAssertions(unittest.TestCase):

    def test_meets_pass(self):
        runs = [_run(duration=100) for _ in range(10)]
        report = compute_sla(runs, SlaTarget(600, 95))
        assert_meets_sla(report)

    def test_meets_fail(self):
        runs = [_run(duration=900) for _ in range(10)]
        report = compute_sla(runs, SlaTarget(600, 95))
        with self.assertRaises(SlaTrackerError):
            assert_meets_sla(report)

    def test_rejects_non_report(self):
        with self.assertRaises(SlaTrackerError):
            assert_meets_sla("nope")  # type: ignore[arg-type]


class TestMarkdown(unittest.TestCase):

    def test_renders(self):
        runs = [_run(duration=100), _run(duration=900)]
        report = compute_sla(runs, SlaTarget(600, 95))
        md = report_markdown(report)
        self.assertIn("SLA", md)
        self.assertIn("50.0", md)

    def test_rejects_non_report(self):
        with self.assertRaises(SlaTrackerError):
            report_markdown("nope")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
