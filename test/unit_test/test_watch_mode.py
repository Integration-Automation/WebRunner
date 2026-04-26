import tempfile
import unittest
from pathlib import Path

from je_web_runner.utils.watch_mode import (
    WatchModeError,
    poll_changes,
    snapshot_dir,
    watch_loop,
)


class TestSnapshot(unittest.TestCase):

    def test_snapshot_picks_up_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "a.json").write_text("{}", encoding="utf-8")
            (Path(tmpdir) / "ignored.txt").write_text("x", encoding="utf-8")
            snap = snapshot_dir(tmpdir)
            keys = list(snap.entries.keys())
            self.assertEqual(len(keys), 1)
            self.assertTrue(keys[0].endswith("a.json"))

    def test_missing_dir_raises(self):
        with self.assertRaises(WatchModeError):
            snapshot_dir("nope")


class TestDiff(unittest.TestCase):

    def test_added_removed_changed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "a.json").write_text("{}", encoding="utf-8")
            (Path(tmpdir) / "b.json").write_text("{}", encoding="utf-8")
            before = snapshot_dir(tmpdir)
            (Path(tmpdir) / "a.json").write_text("{\"k\":1}", encoding="utf-8")
            (Path(tmpdir) / "b.json").unlink()
            (Path(tmpdir) / "c.json").write_text("{}", encoding="utf-8")
            after = snapshot_dir(tmpdir)
            diff = poll_changes(before, after)
            self.assertEqual(len(diff.added), 1)
            self.assertEqual(len(diff.removed), 1)
            self.assertEqual(len(diff.changed), 1)


class TestWatchLoop(unittest.TestCase):

    def test_runs_callback_on_change(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "a.json").write_text("{}", encoding="utf-8")
            calls = []
            sleep_count = {"n": 0}

            def fake_sleep(_s):
                sleep_count["n"] += 1
                if sleep_count["n"] == 2:
                    (Path(tmpdir) / "b.json").write_text("{}", encoding="utf-8")

            iterations = watch_loop(
                tmpdir,
                on_change=lambda diff: calls.append(diff),
                interval=0,
                max_iterations=3,
                sleep=fake_sleep,
            )
            self.assertEqual(iterations, 3)
            self.assertEqual(len(calls), 1)
            added_paths = calls[0].added
            self.assertTrue(any(p.endswith("b.json") for p in added_paths))


if __name__ == "__main__":
    unittest.main()
