import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from je_web_runner.utils.cli.watch_mode import watch_directory


class TestWatchMode(unittest.TestCase):

    def test_initial_run_fires(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = MagicMock()
            runs = watch_directory(tmpdir, runner, poll_seconds=0.01,
                                   debounce_seconds=0.01, iterations=1)
            self.assertEqual(runs, 1)
            runner.assert_called_once()

    def test_change_triggers_re_run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            initial = Path(tmpdir) / "a.json"
            initial.write_text("[]", encoding="utf-8")

            calls = {"count": 0}

            def runner():
                calls["count"] += 1
                if calls["count"] == 1:
                    # Mutate the file just after the first (initial) run; the
                    # next poll iteration will see the new mtime and fire.
                    time.sleep(0.05)
                    initial.write_text("[[\"WR_quit\"]]", encoding="utf-8")

            runs = watch_directory(tmpdir, runner, poll_seconds=0.05,
                                   debounce_seconds=0.05, iterations=4)
            self.assertGreaterEqual(runs, 2)

    def test_missing_directory_raises(self):
        with self.assertRaises(FileNotFoundError):
            watch_directory("/no/such/dir", lambda: None, iterations=1)


if __name__ == "__main__":
    unittest.main()
