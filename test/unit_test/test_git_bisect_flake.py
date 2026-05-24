"""Unit tests for je_web_runner.utils.git_bisect_flake."""
import json
import tempfile
import unittest
from pathlib import Path

from je_web_runner.utils.git_bisect_flake.bisect import (
    BisectResult,
    GitBisectFlakeError,
    LedgerEntry,
    bisect_from_ledger,
    bisect_with_probe,
    load_ledger,
    report_markdown,
)


def _ledger(*rows):
    return [LedgerEntry(**r) for r in rows]


def _row(commit, passed, test_id="t1"):
    return {"commit": commit, "test_id": test_id, "passed": passed}


class TestLedgerEntry(unittest.TestCase):

    def test_rejects_empty_commit(self):
        with self.assertRaises(GitBisectFlakeError):
            LedgerEntry(commit="", test_id="t", passed=True)

    def test_rejects_empty_test_id(self):
        with self.assertRaises(GitBisectFlakeError):
            LedgerEntry(commit="c", test_id="", passed=True)


class TestLoadLedger(unittest.TestCase):

    def test_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "l.json"
            path.write_text(json.dumps({"runs": [
                {"commit": "c1", "test_id": "t1", "passed": True},
                {"commit": "c2", "path": "t1", "passed": False},
            ]}), encoding="utf-8")
            entries = load_ledger(path)
            self.assertEqual(len(entries), 2)
            self.assertEqual(entries[1].test_id, "t1")

    def test_missing(self):
        with self.assertRaises(GitBisectFlakeError):
            load_ledger("/no/such/ledger.json")

    def test_bad_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "l.json"
            p.write_text("nope", encoding="utf-8")
            with self.assertRaises(GitBisectFlakeError):
                load_ledger(p)

    def test_missing_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "l.json"
            p.write_text(json.dumps({"x": []}), encoding="utf-8")
            with self.assertRaises(GitBisectFlakeError):
                load_ledger(p)


class TestBisectFromLedger(unittest.TestCase):

    def test_finds_boundary(self):
        order = ["c1", "c2", "c3", "c4", "c5"]
        entries = _ledger(
            _row("c1", True), _row("c2", True),
            _row("c3", False), _row("c4", False), _row("c5", False),
        )
        result = bisect_from_ledger(entries, order, "t1")
        self.assertEqual(result.last_good_commit, "c2")
        self.assertEqual(result.first_bad_commit, "c3")
        self.assertEqual(result.method, "ledger")

    def test_always_failing(self):
        order = ["c1", "c2"]
        entries = _ledger(_row("c1", False), _row("c2", False))
        result = bisect_from_ledger(entries, order, "t1")
        self.assertIsNone(result.last_good_commit)
        # First-bad is the earliest failing commit
        self.assertEqual(result.first_bad_commit, "c1")

    def test_still_passing(self):
        order = ["c1", "c2"]
        entries = _ledger(_row("c1", True), _row("c2", True))
        result = bisect_from_ledger(entries, order, "t1")
        self.assertEqual(result.last_good_commit, "c2")
        self.assertIsNone(result.first_bad_commit)

    def test_skips_unmatched_test(self):
        order = ["c1"]
        entries = _ledger(_row("c1", True, test_id="other"))
        with self.assertRaises(GitBisectFlakeError):
            bisect_from_ledger(entries, order, "t1")

    def test_empty_entries(self):
        with self.assertRaises(GitBisectFlakeError):
            bisect_from_ledger([], ["c1"], "t1")

    def test_empty_order(self):
        with self.assertRaises(GitBisectFlakeError):
            bisect_from_ledger(_ledger(_row("c1", True)), [], "t1")

    def test_empty_test_id(self):
        with self.assertRaises(GitBisectFlakeError):
            bisect_from_ledger(_ledger(_row("c1", True)), ["c1"], "")

    def test_gaps_in_order_skipped(self):
        # ledger has c2 but order also includes unrun c1.5; skip silently
        order = ["c1", "c2", "c3"]
        entries = _ledger(_row("c1", True), _row("c3", False))
        result = bisect_from_ledger(entries, order, "t1")
        self.assertEqual(result.last_good_commit, "c1")
        self.assertEqual(result.first_bad_commit, "c3")


class TestBisectWithProbe(unittest.TestCase):

    def test_finds_boundary(self):
        order = ["c1", "c2", "c3", "c4", "c5", "c6", "c7", "c8"]
        # bad starting at c5
        passing = {c: i < 4 for i, c in enumerate(order)}

        def probe(commit):
            return passing[commit]

        result = bisect_with_probe(order, "t1", probe)
        self.assertEqual(result.last_good_commit, "c4")
        self.assertEqual(result.first_bad_commit, "c5")
        self.assertLessEqual(result.probes, 4)  # log2(8)
        self.assertEqual(result.method, "probe")

    def test_uses_known_bounds(self):
        order = ["c1", "c2", "c3", "c4", "c5"]
        passing = {"c1": True, "c2": True, "c3": True, "c4": False, "c5": False}
        probes_made = []

        def probe(commit):
            probes_made.append(commit)
            return passing[commit]

        result = bisect_with_probe(order, "t1", probe,
                                   known_good="c2", known_bad="c5")
        self.assertEqual(result.last_good_commit, "c3")
        self.assertEqual(result.first_bad_commit, "c4")
        # All probes within [c3, c4]
        self.assertTrue(all(c in {"c3", "c4"} for c in probes_made))

    def test_invalid_bounds(self):
        order = ["c1", "c2", "c3"]
        with self.assertRaises(GitBisectFlakeError):
            bisect_with_probe(order, "t1", lambda c: True, known_good="missing")
        with self.assertRaises(GitBisectFlakeError):
            bisect_with_probe(order, "t1", lambda c: True, known_bad="missing")
        with self.assertRaises(GitBisectFlakeError):
            bisect_with_probe(order, "t1", lambda c: True,
                              known_good="c3", known_bad="c1")

    def test_short_order(self):
        with self.assertRaises(GitBisectFlakeError):
            bisect_with_probe(["c1"], "t1", lambda c: True)

    def test_empty_test_id(self):
        with self.assertRaises(GitBisectFlakeError):
            bisect_with_probe(["c1", "c2"], "", lambda c: True)

    def test_probe_failure(self):
        def boom(_):
            raise RuntimeError("checkout failed")
        with self.assertRaises(GitBisectFlakeError):
            bisect_with_probe(["c1", "c2", "c3"], "t1", boom)


class TestReport(unittest.TestCase):

    def test_render_with_boundary(self):
        result = BisectResult(
            test_id="t1", last_good_commit="abcd1234",
            first_bad_commit="efgh5678", probes=3, method="probe",
            history=[{"commit": "abcd1234", "passed": True}],
        )
        md = report_markdown(result)
        self.assertIn("abcd1234", md)
        self.assertIn("efgh5678", md)
        self.assertIn("3 probes", md)

    def test_render_no_boundary(self):
        result = BisectResult(
            test_id="t1", last_good_commit=None, first_bad_commit=None,
        )
        self.assertIn("not flipped", report_markdown(result))

    def test_rejects_non_result(self):
        with self.assertRaises(GitBisectFlakeError):
            report_markdown("not a result")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
