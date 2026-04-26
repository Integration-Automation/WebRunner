import os
import tempfile
import unittest

from je_web_runner.utils.run_ledger.flaky import (
    FlakyDetectorError,
    flaky_paths,
    flakiness_stats,
)
from je_web_runner.utils.run_ledger.ledger import record_run


class TestFlakinessStats(unittest.TestCase):

    def test_consistent_pass_not_flaky(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "ledger.json")
            for _ in range(5):
                record_run(path, "stable.json", True)
            stats = flakiness_stats(path)
            self.assertFalse(stats["stable.json"]["flaky"])
            self.assertEqual(stats["stable.json"]["passes"], 5)

    def test_mixed_history_flaky(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "ledger.json")
            record_run(path, "wobbly.json", True)
            record_run(path, "wobbly.json", False)
            record_run(path, "wobbly.json", True)
            self.assertTrue(flakiness_stats(path)["wobbly.json"]["flaky"])

    def test_min_runs_threshold(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "ledger.json")
            record_run(path, "x.json", True)
            record_run(path, "x.json", False)
            self.assertFalse(flakiness_stats(path, min_runs=5)["x.json"]["flaky"])
            self.assertTrue(flakiness_stats(path, min_runs=2)["x.json"]["flaky"])

    def test_no_ledger_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "missing.json")
            self.assertEqual(flakiness_stats(path), {})


class TestFlakyPaths(unittest.TestCase):

    def test_returns_only_flaky(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "ledger.json")
            for _ in range(3):
                record_run(path, "stable.json", True)
            record_run(path, "wobbly.json", True)
            record_run(path, "wobbly.json", False)
            record_run(path, "wobbly.json", True)
            self.assertEqual(flaky_paths(path, min_runs=3), ["wobbly.json"])

    def test_min_fail_rate_filters(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "ledger.json")
            record_run(path, "wobbly.json", True)
            record_run(path, "wobbly.json", True)
            record_run(path, "wobbly.json", False)
            self.assertEqual(flaky_paths(path, min_runs=3, min_fail_rate=0.5), [])
            self.assertEqual(flaky_paths(path, min_runs=3, min_fail_rate=0.2), ["wobbly.json"])


class TestErrorHandling(unittest.TestCase):

    def test_invalid_json_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "ledger.json")
            with open(path, "w", encoding="utf-8") as ledger_file:
                ledger_file.write("not json")
            with self.assertRaises(FlakyDetectorError):
                flakiness_stats(path)


if __name__ == "__main__":
    unittest.main()
