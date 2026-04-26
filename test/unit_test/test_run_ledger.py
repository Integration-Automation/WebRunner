import json
import os
import tempfile
import unittest
from pathlib import Path

from je_web_runner.utils.run_ledger.ledger import (
    LedgerError,
    clear_ledger,
    failed_files,
    latest_status,
    passed_files,
    record_run,
)


class TestLedger(unittest.TestCase):

    def test_record_creates_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "ledger.json")
            record_run(path, "tests/a.json", True)
            self.assertTrue(os.path.exists(path))

    def test_latest_status_uses_most_recent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "ledger.json")
            record_run(path, "tests/a.json", True)
            record_run(path, "tests/a.json", False)
            self.assertEqual(latest_status(path), {"tests/a.json": False})

    def test_failed_and_passed_lists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "ledger.json")
            record_run(path, "a.json", True)
            record_run(path, "b.json", False)
            record_run(path, "c.json", True)
            self.assertEqual(set(failed_files(path)), {"b.json"})
            self.assertEqual(set(passed_files(path)), {"a.json", "c.json"})

    def test_invalid_ledger_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "ledger.json")
            Path(path).write_text("not json", encoding="utf-8")
            with self.assertRaises(LedgerError):
                record_run(path, "a.json", True)

    def test_missing_runs_block_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "ledger.json")
            Path(path).write_text(json.dumps({"foo": []}), encoding="utf-8")
            with self.assertRaises(LedgerError):
                record_run(path, "a.json", True)

    def test_clear_removes_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "ledger.json")
            record_run(path, "a.json", True)
            clear_ledger(path)
            self.assertFalse(os.path.exists(path))


if __name__ == "__main__":
    unittest.main()
