"""Unit tests for je_web_runner.utils.flake_detector."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from je_web_runner.utils.flake_detector.detector import (
    FlakeDetectorError,
    QuarantineEntry,
    QuarantineRegistry,
    compute_flake_scores,
    flaky_paths,
    flaky_quarantine,
    quarantine_flaky,
    quarantine_report_markdown,
    release_if_stable,
)


def _write_ledger(path: Path, runs):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fp:
        json.dump({"runs": runs}, fp)


def _iso(dt):
    return dt.replace(tzinfo=timezone.utc).isoformat(timespec="seconds")


class TestComputeFlakeScores(unittest.TestCase):

    def test_missing_ledger_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self.assertEqual(compute_flake_scores(Path(tmpdir) / "x.json"), {})

    def test_bad_ledger_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "x.json"
            path.write_text("[]", encoding="utf-8")
            with self.assertRaises(FlakeDetectorError):
                compute_flake_scores(path)

    def test_stable_test_is_not_flaky(self):
        now = datetime.now(timezone.utc)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "l.json"
            _write_ledger(path, [
                {"path": "t1.json", "passed": True, "time": _iso(now)},
                {"path": "t1.json", "passed": True, "time": _iso(now)},
                {"path": "t1.json", "passed": True, "time": _iso(now)},
            ])
            scores = compute_flake_scores(path)
            self.assertFalse(scores["t1.json"].is_flaky)
            self.assertEqual(scores["t1.json"].flake_score, 0.0)
            self.assertEqual(scores["t1.json"].pass_rate, 1.0)

    def test_alternating_test_is_flaky(self):
        now = datetime.now(timezone.utc)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "l.json"
            _write_ledger(path, [
                {"path": "t2.json", "passed": True, "time": _iso(now)},
                {"path": "t2.json", "passed": False, "time": _iso(now)},
                {"path": "t2.json", "passed": True, "time": _iso(now)},
                {"path": "t2.json", "passed": False, "time": _iso(now)},
            ])
            scores = compute_flake_scores(path)
            self.assertTrue(scores["t2.json"].is_flaky)
            self.assertGreater(scores["t2.json"].flake_score, 0.4)

    def test_decay_weights_old_failures_less(self):
        now = datetime.now(timezone.utc)
        old = now - timedelta(days=60)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "l.json"
            _write_ledger(path, [
                {"path": "t3.json", "passed": False, "time": _iso(old)},
                {"path": "t3.json", "passed": False, "time": _iso(old)},
                {"path": "t3.json", "passed": True, "time": _iso(now)},
                {"path": "t3.json", "passed": True, "time": _iso(now)},
                {"path": "t3.json", "passed": True, "time": _iso(now)},
            ])
            scores = compute_flake_scores(path, half_life_days=7.0)
            # 2/5 unweighted ≈ 0.4 fails, but recent successes weigh more, so
            # decayed score should be well below 0.4
            self.assertLess(scores["t3.json"].flake_score, 0.3)

    def test_min_runs_gates_flag(self):
        now = datetime.now(timezone.utc)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "l.json"
            _write_ledger(path, [
                {"path": "t4.json", "passed": True, "time": _iso(now)},
                {"path": "t4.json", "passed": False, "time": _iso(now)},
            ])
            scores = compute_flake_scores(path, min_runs=3)
            self.assertFalse(scores["t4.json"].is_flaky)


class TestFlakyPaths(unittest.TestCase):

    def test_returns_flaky_only_sorted(self):
        now = datetime.now(timezone.utc)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "l.json"
            _write_ledger(path, [
                {"path": "a.json", "passed": True, "time": _iso(now)},
                {"path": "a.json", "passed": True, "time": _iso(now)},
                {"path": "a.json", "passed": True, "time": _iso(now)},
                {"path": "b.json", "passed": True, "time": _iso(now)},
                {"path": "b.json", "passed": False, "time": _iso(now)},
                {"path": "b.json", "passed": False, "time": _iso(now)},
                {"path": "c.json", "passed": True, "time": _iso(now)},
                {"path": "c.json", "passed": False, "time": _iso(now)},
                {"path": "c.json", "passed": False, "time": _iso(now)},
                {"path": "c.json", "passed": False, "time": _iso(now)},
            ])
            result = flaky_paths(path)
            self.assertNotIn("a.json", result)
            self.assertIn("b.json", result)
            self.assertIn("c.json", result)
            # c has higher fail rate so it should come first
            self.assertEqual(result[0], "c.json")


class TestQuarantineRegistry(unittest.TestCase):

    def test_round_trips_through_disk(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            registry_path = Path(tmpdir) / "q.json"
            reg = QuarantineRegistry(registry_path)
            self.assertFalse(reg.is_quarantined("t.json"))
            reg.add(QuarantineEntry(
                test_id="t.json", reason="manual", flake_score=0.6,
                quarantined_at="2026-01-01T00:00:00+00:00",
            ))
            # re-read from disk
            reg2 = QuarantineRegistry(registry_path)
            self.assertTrue(reg2.is_quarantined("t.json"))
            self.assertEqual(reg2.get("t.json").reason, "manual")

    def test_remove_returns_false_for_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reg = QuarantineRegistry(Path(tmpdir) / "q.json")
            self.assertFalse(reg.remove("nope"))

    def test_bad_registry_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            registry_path = Path(tmpdir) / "q.json"
            registry_path.write_text("[]", encoding="utf-8")
            with self.assertRaises(FlakeDetectorError):
                QuarantineRegistry(registry_path)

    def test_list_is_sorted_by_score_desc(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reg = QuarantineRegistry(Path(tmpdir) / "q.json")
            reg.add(QuarantineEntry("a", "x", 0.3, "2026-01-01T00:00:00+00:00"))
            reg.add(QuarantineEntry("b", "x", 0.7, "2026-01-01T00:00:00+00:00"))
            reg.add(QuarantineEntry("c", "x", 0.5, "2026-01-01T00:00:00+00:00"))
            self.assertEqual([e.test_id for e in reg.list()], ["b", "c", "a"])


class TestQuarantineFlaky(unittest.TestCase):

    def test_adds_new_flaky_tests(self):
        now = datetime.now(timezone.utc)
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "l.json"
            _write_ledger(ledger, [
                {"path": "f.json", "passed": p, "time": _iso(now)}
                for p in (True, False, True, False, False)
            ])
            registry = Path(tmpdir) / "q.json"
            added = quarantine_flaky(ledger, registry)
            self.assertEqual(added, ["f.json"])
            # idempotent on second call
            added2 = quarantine_flaky(ledger, registry)
            self.assertEqual(added2, [])


class TestReleaseIfStable(unittest.TestCase):

    def test_releases_once_stable(self):
        now = datetime.now(timezone.utc)
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "l.json"
            _write_ledger(ledger, [
                {"path": "f.json", "passed": True, "time": _iso(now)} for _ in range(8)
            ])
            registry = Path(tmpdir) / "q.json"
            reg = QuarantineRegistry(registry)
            reg.add(QuarantineEntry(
                "f.json", "auto", 0.5, _iso(now), runs_when_added=4,
            ))
            released = release_if_stable(ledger, registry, min_runs_since=5)
            self.assertEqual(released, ["f.json"])
            self.assertFalse(QuarantineRegistry(registry).is_quarantined("f.json"))

    def test_keeps_if_still_flaky(self):
        now = datetime.now(timezone.utc)
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "l.json"
            _write_ledger(ledger, [
                {"path": "f.json", "passed": p, "time": _iso(now)}
                for p in (True, False, True, False, False, True)
            ])
            registry = Path(tmpdir) / "q.json"
            reg = QuarantineRegistry(registry)
            reg.add(QuarantineEntry("f.json", "auto", 0.5, _iso(now)))
            released = release_if_stable(ledger, registry)
            self.assertEqual(released, [])


class TestFlakyQuarantineDecorator(unittest.TestCase):

    def test_passes_through_when_not_quarantined(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = Path(tmpdir) / "q.json"
            calls = []

            @flaky_quarantine("test_clean", registry)
            def test_clean():
                calls.append(1)
                return "ok"

            self.assertEqual(test_clean(), "ok")
            self.assertEqual(calls, [1])

    def test_skips_when_quarantined_and_pytest_available(self):
        try:
            import pytest  # noqa: F401
        except ImportError:
            self.skipTest("pytest not installed")
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = Path(tmpdir) / "q.json"
            reg = QuarantineRegistry(registry)
            reg.add(QuarantineEntry(
                "test_q", "auto", 0.5, "2026-01-01T00:00:00+00:00",
            ))

            @flaky_quarantine("test_q", registry)
            def test_q():
                return "should not run"

            with self.assertRaises(Exception) as cm:
                test_q()
            # pytest.skip raises pytest.skip.Exception; just make sure something
            # was raised and the reason is in the message.
            self.assertIn("flaky-quarantine", str(cm.exception))

    def test_skip_disabled_runs_the_test(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = Path(tmpdir) / "q.json"
            reg = QuarantineRegistry(registry)
            reg.add(QuarantineEntry(
                "test_q", "auto", 0.5, "2026-01-01T00:00:00+00:00",
            ))

            @flaky_quarantine("test_q", registry, skip_when_quarantined=False)
            def test_q():
                return "ran"

            self.assertEqual(test_q(), "ran")


class TestReport(unittest.TestCase):

    def test_empty_registry_renders_placeholder(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            md = quarantine_report_markdown(QuarantineRegistry(Path(tmpdir) / "q.json"))
            self.assertIn("No quarantined", md)

    def test_renders_table(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reg = QuarantineRegistry(Path(tmpdir) / "q.json")
            reg.add(QuarantineEntry("a.json", "manual", 0.6, "2026-01-01T00:00:00+00:00"))
            md = quarantine_report_markdown(reg)
            self.assertIn("`a.json`", md)
            self.assertIn("0.60", md)


if __name__ == "__main__":
    unittest.main()
