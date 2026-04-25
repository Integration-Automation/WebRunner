import os
import tempfile
import unittest

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.snapshot.snapshot import (
    SnapshotMismatch,
    delete_snapshot,
    match_snapshot,
    update_snapshot,
)


class TestSnapshot(unittest.TestCase):

    def test_first_run_creates_baseline(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self.assertEqual(match_snapshot("home", "hello", tmpdir), "created")
            self.assertTrue(os.path.exists(os.path.join(tmpdir, "home.snap")))

    def test_second_run_matches(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            match_snapshot("home", "hello", tmpdir)
            self.assertEqual(match_snapshot("home", "hello", tmpdir), "matched")

    def test_mismatch_raises_with_diff(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            match_snapshot("home", "hello\nworld\n", tmpdir)
            with self.assertRaises(SnapshotMismatch) as ctx:
                match_snapshot("home", "hello\nplanet\n", tmpdir)
            self.assertIn("planet", str(ctx.exception))

    def test_update_overwrites(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            match_snapshot("home", "v1", tmpdir)
            update_snapshot("home", "v2", tmpdir)
            self.assertEqual(match_snapshot("home", "v2", tmpdir), "matched")

    def test_delete_returns_true_when_existed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            match_snapshot("home", "v1", tmpdir)
            self.assertTrue(delete_snapshot("home", tmpdir))
            self.assertFalse(delete_snapshot("home", tmpdir))

    def test_non_string_value_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(WebRunnerException):
                # Intentionally non-str so we exercise the type guard;
                # SonarCloud S5655 is a false positive on this fixture.
                match_snapshot("x", 42, tmpdir)  # type: ignore[arg-type]

    def test_unsafe_chars_in_name_sanitised(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            match_snapshot("a/b\\c", "v", tmpdir)
            self.assertTrue(any(name.endswith(".snap") for name in os.listdir(tmpdir)))


if __name__ == "__main__":
    unittest.main()
