"""Unit tests for je_web_runner.utils.quarantine_age_report."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from je_web_runner.utils.quarantine_age_report.report import (
    AgedEntry,
    AgeReport,
    EscalationTier,
    QuarantineAgeReportError,
    age_entries,
    assert_no_abandoned,
    build_report,
    load_and_age,
    report_markdown,
)

_NOW = datetime(2026, 5, 24, tzinfo=timezone.utc)


def _entry(test_id, days_ago, score=0.5):
    when = _NOW - timedelta(days=days_ago)
    return {
        "test_id": test_id,
        "reason": "flaky",
        "flake_score": score,
        "quarantined_at": when.isoformat(timespec="seconds"),
        "runs_when_added": 10,
    }


class TestAgeEntries(unittest.TestCase):

    def test_tiers(self):
        rows = [
            _entry("fresh", 3),
            _entry("lingering", 14),
            _entry("stale", 45),
            _entry("abandoned", 120),
        ]
        aged = age_entries(rows, now=_NOW)
        tier_by_id = {e.test_id: e.tier for e in aged}
        self.assertEqual(tier_by_id["fresh"], EscalationTier.FRESH)
        self.assertEqual(tier_by_id["lingering"], EscalationTier.LINGERING)
        self.assertEqual(tier_by_id["stale"], EscalationTier.STALE)
        self.assertEqual(tier_by_id["abandoned"], EscalationTier.ABANDONED)

    def test_z_timezone(self):
        rows = [{
            "test_id": "x", "reason": "",
            "flake_score": 0.1,
            "quarantined_at": "2026-05-01T00:00:00Z",
        }]
        aged = age_entries(rows, now=_NOW)
        self.assertEqual(len(aged), 1)
        self.assertGreater(aged[0].age_days, 20)

    def test_skips_non_dict(self):
        aged = age_entries(["not dict", None])  # type: ignore[list-item]
        self.assertEqual(aged, [])

    def test_skips_missing_fields(self):
        rows = [{"test_id": "x"}, {"quarantined_at": "2026-01-01"}]
        self.assertEqual(age_entries(rows, now=_NOW), [])

    def test_naive_now_rejected(self):
        with self.assertRaises(QuarantineAgeReportError):
            age_entries([_entry("x", 1)], now=datetime(2026, 5, 24))

    def test_bad_timestamp_rejected(self):
        rows = [{"test_id": "x", "reason": "", "flake_score": 0,
                 "quarantined_at": "garbage"}]
        with self.assertRaises(QuarantineAgeReportError):
            age_entries(rows, now=_NOW)


class TestBuildReport(unittest.TestCase):

    def test_counts(self):
        aged = age_entries([_entry("a", 1), _entry("b", 100)], now=_NOW)
        report = build_report(aged)
        self.assertEqual(report.total_entries, 2)
        self.assertEqual(report.by_tier["fresh"], 1)
        self.assertEqual(report.by_tier["abandoned"], 1)
        self.assertEqual(report.abandoned, ["b"])

    def test_rejects_non_entry(self):
        with self.assertRaises(QuarantineAgeReportError):
            build_report(["nope"])  # type: ignore[list-item]


class TestLoadAndAge(unittest.TestCase):

    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "registry.json"
            path.write_text(json.dumps({
                "updated_at": "2026-05-24",
                "entries": [_entry("x", 5), _entry("y", 200)],
            }), encoding="utf-8")
            report = load_and_age(path, now=_NOW)
            self.assertEqual(report.total_entries, 2)

    def test_missing_file(self):
        with self.assertRaises(QuarantineAgeReportError):
            load_and_age("/no/such/file.json")

    def test_bad_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.json"
            p.write_text("nope", encoding="utf-8")
            with self.assertRaises(QuarantineAgeReportError):
                load_and_age(p)

    def test_missing_entries_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.json"
            p.write_text(json.dumps({"x": 1}), encoding="utf-8")
            with self.assertRaises(QuarantineAgeReportError):
                load_and_age(p)

    def test_entries_not_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.json"
            p.write_text(json.dumps({"entries": "x"}), encoding="utf-8")
            with self.assertRaises(QuarantineAgeReportError):
                load_and_age(p)


class TestMarkdown(unittest.TestCase):

    def test_renders(self):
        report = build_report(age_entries(
            [_entry("a", 1), _entry("b", 200)], now=_NOW,
        ))
        md = report_markdown(report)
        self.assertIn("Quarantine age report", md)
        self.assertIn("abandoned", md)
        self.assertIn("`b`", md)

    def test_caps_top_n(self):
        rows = [_entry(f"t{i}", 200) for i in range(20)]
        report = build_report(age_entries(rows, now=_NOW))
        md = report_markdown(report, top_n=5)
        self.assertIn("+15 more", md)

    def test_bad_top_n(self):
        with self.assertRaises(QuarantineAgeReportError):
            report_markdown(AgeReport(), top_n=-1)

    def test_rejects_non_report(self):
        with self.assertRaises(QuarantineAgeReportError):
            report_markdown("nope")  # type: ignore[arg-type]


class TestAssertNoAbandoned(unittest.TestCase):

    def test_pass(self):
        assert_no_abandoned(AgeReport())

    def test_fail(self):
        report = build_report(age_entries([_entry("x", 200)], now=_NOW))
        with self.assertRaises(QuarantineAgeReportError):
            assert_no_abandoned(report)

    def test_rejects_non_report(self):
        with self.assertRaises(QuarantineAgeReportError):
            assert_no_abandoned("nope")  # type: ignore[arg-type]


class TestAgedEntryDict(unittest.TestCase):

    def test_to_dict_serialises_tier(self):
        aged = age_entries([_entry("x", 1)], now=_NOW)[0]
        self.assertIn(aged.to_dict()["tier"], ("fresh", "lingering", "stale", "abandoned"))


if __name__ == "__main__":
    unittest.main()
