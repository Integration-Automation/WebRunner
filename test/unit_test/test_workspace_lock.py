import datetime as _dt
import json
import tempfile
import unittest
from pathlib import Path

from je_web_runner.utils.workspace_lock import (
    LockEntry,
    WorkspaceLock,
    WorkspaceLockError,
    load_lock,
    write_lock,
)
from je_web_runner.utils.workspace_lock.lock import (
    build_lock,
    diff_locks,
)


class TestBuildLock(unittest.TestCase):

    def test_python_version_recorded(self):
        lock = build_lock(allow_distributions=["selenium"])
        self.assertTrue(lock.python_version.startswith("3."))
        # Build doesn't crash if 'selenium' isn't installed; check shape.
        for entry in lock.entries:
            self.assertEqual(entry.kind, "python")

    def test_drivers_appended(self):
        lock = build_lock(
            drivers=[{
                "name": "geckodriver",
                "version": "0.34.0",
                "url": "https://e.com/g.zip",
            }],
            allow_distributions=[],
        )
        driver_entries = lock.by_kind("driver")
        self.assertEqual(driver_entries[0].name, "geckodriver")
        self.assertEqual(driver_entries[0].extras["url"], "https://e.com/g.zip")

    def test_invalid_driver_raises(self):
        with self.assertRaises(WorkspaceLockError):
            build_lock(drivers=[{"name": "x"}])

    def test_playwright_browser_versions(self):
        lock = build_lock(
            playwright_versions={"chromium": "127.0.0.0"},
            allow_distributions=[],
        )
        playwright = lock.by_kind("playwright")
        self.assertEqual(playwright[0].version, "127.0.0.0")

    def test_invalid_playwright_value(self):
        with self.assertRaises(WorkspaceLockError):
            build_lock(
                playwright_versions={"chromium": 127},  # type: ignore[dict-item]
                allow_distributions=[],
            )

    def test_generated_at_isoformat(self):
        when = _dt.datetime(2026, 4, 26, 12, 0, 0, tzinfo=_dt.timezone.utc)
        lock = build_lock(allow_distributions=[], now=when)
        self.assertEqual(lock.generated_at, "2026-04-26T12:00:00+00:00")


class TestWriteAndLoad(unittest.TestCase):

    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "lock.json"
            lock = WorkspaceLock(
                python_version="3.12.0",
                generated_at="2026-04-26T12:00:00+00:00",
                entries=[LockEntry(name="selenium", version="4.20", kind="python")],
            )
            write_lock(lock, path)
            loaded = load_lock(path)
            self.assertEqual(loaded.python_version, "3.12.0")
            self.assertEqual(loaded.entries[0].name, "selenium")

    def test_load_missing_raises(self):
        with self.assertRaises(WorkspaceLockError):
            load_lock("does/not/exist.json")

    def test_load_invalid_json_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "lock.json"
            path.write_text("not json", encoding="utf-8")
            with self.assertRaises(WorkspaceLockError):
                load_lock(path)

    def test_entries_must_be_list(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "lock.json"
            path.write_text(json.dumps({"entries": "no"}), encoding="utf-8")
            with self.assertRaises(WorkspaceLockError):
                load_lock(path)

    def test_entry_missing_field(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "lock.json"
            path.write_text(json.dumps({"entries": [{"name": "x"}]}), encoding="utf-8")
            with self.assertRaises(WorkspaceLockError):
                load_lock(path)


class TestDiffLocks(unittest.TestCase):

    def test_added_removed_changed(self):
        before = WorkspaceLock(
            python_version="3.12.0",
            generated_at="t0",
            entries=[
                LockEntry(name="a", version="1", kind="python"),
                LockEntry(name="b", version="2", kind="python"),
            ],
        )
        after = WorkspaceLock(
            python_version="3.12.0",
            generated_at="t1",
            entries=[
                LockEntry(name="a", version="1", kind="python"),
                LockEntry(name="b", version="3", kind="python"),
                LockEntry(name="c", version="0.1", kind="python"),
            ],
        )
        diff = diff_locks(before, after)
        self.assertEqual(len(diff["added"]), 1)
        self.assertEqual(diff["added"][0]["name"], "c")
        self.assertEqual(diff["version_changed"][0]["name"], "b")
        self.assertEqual(diff["version_changed"][0]["to"], "3")
        self.assertEqual(diff["removed"], [])


if __name__ == "__main__":
    unittest.main()
