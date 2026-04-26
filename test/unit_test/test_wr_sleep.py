import time
import unittest

from je_web_runner.utils.executor.action_executor import (
    _sleep_seconds,
    execute_action,
    executor,
)


class TestSleepSeconds(unittest.TestCase):

    def test_zero_seconds_returns_immediately(self):
        start = time.monotonic()
        result = _sleep_seconds(0)
        self.assertLess(time.monotonic() - start, 0.05)
        self.assertEqual(result, 0.0)

    def test_short_sleep_blocks(self):
        start = time.monotonic()
        _sleep_seconds(0.1)
        elapsed = time.monotonic() - start
        self.assertGreaterEqual(elapsed, 0.09)

    def test_negative_raises(self):
        with self.assertRaises(ValueError):
            _sleep_seconds(-1)

    def test_non_number_raises(self):
        with self.assertRaises(ValueError):
            _sleep_seconds("two")  # type: ignore[arg-type]

    def test_bool_rejected(self):
        # bool is technically int but is almost always a typo here
        with self.assertRaises(ValueError):
            _sleep_seconds(True)  # type: ignore[arg-type]


class TestExecutorRegistration(unittest.TestCase):

    def test_wr_sleep_present(self):
        self.assertIn("WR_sleep", executor.event_dict)

    def test_action_json_short_sleep(self):
        start = time.monotonic()
        result = execute_action([["WR_sleep", {"seconds": 0.05}]])
        elapsed = time.monotonic() - start
        self.assertGreaterEqual(elapsed, 0.04)
        # The executor returns ``{verbose-key: result}`` keyed on a
        # human-readable representation of the action.
        self.assertEqual(list(result.values()), [0.05])


if __name__ == "__main__":
    unittest.main()
