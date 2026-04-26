import time
import unittest

from je_web_runner.utils.fanout import (
    FanOutError,
    run_fan_out,
)


class TestRunFanOut(unittest.TestCase):

    def test_runs_all_in_parallel(self):
        result = run_fan_out([
            lambda: 1,
            lambda: 2,
            lambda: 3,
        ])
        self.assertTrue(result.succeeded)
        names = sorted(o.name for o in result.outcomes)
        self.assertEqual(names, ["task-0", "task-1", "task-2"])

    def test_named_tasks(self):
        result = run_fan_out([
            ("preflight-a", lambda: "ok-a"),
            ("preflight-b", lambda: "ok-b"),
        ])
        names = sorted(o.name for o in result.outcomes)
        self.assertEqual(names, ["preflight-a", "preflight-b"])

    def test_failure_recorded(self):
        def boom():
            raise RuntimeError("nope")
        result = run_fan_out([
            ("good", lambda: 1),
            ("bad", boom),
        ])
        self.assertFalse(result.succeeded)
        self.assertEqual(len(result.failures), 1)
        with self.assertRaises(FanOutError):
            result.raise_for_failures()

    def test_to_dict_round_trip(self):
        result = run_fan_out([("x", lambda: 5)])
        payload = result.to_dict()
        self.assertTrue(payload["succeeded"])
        self.assertEqual(payload["outcomes"][0]["result"], 5)

    def test_empty_tasks_raises(self):
        with self.assertRaises(FanOutError):
            run_fan_out([])

    def test_invalid_task_raises(self):
        with self.assertRaises(FanOutError):
            run_fan_out([42])  # type: ignore[list-item]

    def test_actually_runs_in_parallel(self):
        def slow():
            time.sleep(0.05)
            return "ok"
        start = time.monotonic()
        result = run_fan_out([slow, slow, slow], max_workers=3)
        elapsed = time.monotonic() - start
        # Sequential would be ~0.15s; parallel should land well under 0.12s.
        self.assertTrue(result.succeeded)
        self.assertLess(elapsed, 0.12)


if __name__ == "__main__":
    unittest.main()
