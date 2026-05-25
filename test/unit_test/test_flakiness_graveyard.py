"""Unit tests for je_web_runner.utils.flakiness_graveyard."""
import json
import os
import tempfile
import unittest
from datetime import date, timedelta

from je_web_runner.utils.flakiness_graveyard.graveyard import (
    FlakinessGraveyardError,
    GraveEntry,
    Status,
    bury,
    due_for_burial,
    load,
    register_flake,
    revive,
    save,
)


class TestEntry(unittest.TestCase):

    def test_basic(self):
        GraveEntry(test_name="t", quarantined_at="2026-01-01",
                   last_flake_date="2026-01-01")

    def test_empty_name(self):
        with self.assertRaises(FlakinessGraveyardError):
            GraveEntry(test_name="", quarantined_at="2026-01-01",
                       last_flake_date="2026-01-01")

    def test_bad_date(self):
        with self.assertRaises(FlakinessGraveyardError):
            GraveEntry(test_name="t", quarantined_at="not-a-date",
                       last_flake_date="2026-01-01")


class TestRegisterFlake(unittest.TestCase):

    def test_new(self):
        reg = []
        today = date(2026, 1, 10)
        e = register_flake(reg, "t1", owner="alice", today=today)
        self.assertEqual(e.quarantined_at, "2026-01-10")
        self.assertEqual(len(reg), 1)

    def test_update_existing(self):
        reg = [GraveEntry(test_name="t1", quarantined_at="2026-01-01",
                          last_flake_date="2026-01-01")]
        today = date(2026, 1, 15)
        e = register_flake(reg, "t1", today=today)
        self.assertEqual(e.last_flake_date, "2026-01-15")
        self.assertEqual(len(reg), 1)

    def test_revive_then_register(self):
        reg = [GraveEntry(test_name="t1", quarantined_at="2026-01-01",
                          last_flake_date="2026-01-01",
                          status=Status.REVIVED)]
        today = date(2026, 1, 20)
        e = register_flake(reg, "t1", today=today)
        self.assertEqual(e.status, Status.QUARANTINED)
        self.assertEqual(e.quarantined_at, "2026-01-20")

    def test_bad_reg(self):
        with self.assertRaises(FlakinessGraveyardError):
            register_flake("nope", "t")


class TestRevive(unittest.TestCase):

    def test_basic(self):
        reg = [GraveEntry(test_name="t", quarantined_at="2026-01-01",
                          last_flake_date="2026-01-01")]
        e = revive(reg, "t")
        self.assertEqual(e.status, Status.REVIVED)

    def test_unknown(self):
        with self.assertRaises(FlakinessGraveyardError):
            revive([], "missing")

    def test_already_buried(self):
        reg = [GraveEntry(test_name="t", quarantined_at="2026-01-01",
                          last_flake_date="2026-01-01",
                          status=Status.BURIED)]
        with self.assertRaises(FlakinessGraveyardError):
            revive(reg, "t")


class TestDueForBurial(unittest.TestCase):

    def test_due(self):
        reg = [GraveEntry(test_name="old", quarantined_at="2026-01-01",
                          last_flake_date="2026-01-01")]
        due = due_for_burial(reg, days=30,
                             today=date(2026, 2, 10))
        self.assertEqual(len(due), 1)

    def test_not_due(self):
        reg = [GraveEntry(test_name="fresh", quarantined_at="2026-02-01",
                          last_flake_date="2026-02-01")]
        due = due_for_burial(reg, days=30,
                             today=date(2026, 2, 10))
        self.assertEqual(due, [])

    def test_skip_revived(self):
        reg = [GraveEntry(test_name="t", quarantined_at="2026-01-01",
                          last_flake_date="2026-01-01",
                          status=Status.REVIVED)]
        due = due_for_burial(reg, days=30, today=date(2026, 3, 1))
        self.assertEqual(due, [])

    def test_bad_days(self):
        with self.assertRaises(FlakinessGraveyardError):
            due_for_burial([], days=0)


class TestBury(unittest.TestCase):

    def test_basic(self):
        reg = [GraveEntry(test_name="t", quarantined_at="2026-01-01",
                          last_flake_date="2026-01-01")]
        e = bury(reg, "t")
        self.assertEqual(e.status, Status.BURIED)

    def test_already_buried(self):
        reg = [GraveEntry(test_name="t", quarantined_at="2026-01-01",
                          last_flake_date="2026-01-01",
                          status=Status.BURIED)]
        with self.assertRaises(FlakinessGraveyardError):
            bury(reg, "t")

    def test_unknown(self):
        with self.assertRaises(FlakinessGraveyardError):
            bury([], "missing")


class TestSaveLoad(unittest.TestCase):

    def test_roundtrip(self):
        reg = [GraveEntry(test_name="t", quarantined_at="2026-01-01",
                          last_flake_date="2026-01-01", owner="alice")]
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "g.json")
            save(path, reg)
            loaded = load(path)
            self.assertEqual(loaded[0].owner, "alice")

    def test_load_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(load(os.path.join(tmp, "nope.json")), [])

    def test_save_empty_path(self):
        with self.assertRaises(FlakinessGraveyardError):
            save("", [])

    def test_load_bad_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "g.json")
            with open(path, "w") as fh:
                json.dump({"not": "list"}, fh)
            with self.assertRaises(FlakinessGraveyardError):
                load(path)


if __name__ == "__main__":
    unittest.main()
