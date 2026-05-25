"""Unit tests for je_web_runner.utils.web_locks."""
import unittest

from je_web_runner.utils.web_locks.locks import (
    HARVEST_LOG_SCRIPT,
    INSTALL_LISTENER_SCRIPT,
    LockOutcome,
    WebLocksError,
    assert_acquired_count,
    assert_if_available_unavailable,
    assert_no_deadlock,
    assert_serialised,
    parse_log,
)


class TestScripts(unittest.TestCase):

    def test_install_guard(self):
        self.assertIn("__wr_locks_installed__", INSTALL_LISTENER_SCRIPT)
        self.assertIn("navigator.locks", INSTALL_LISTENER_SCRIPT)

    def test_harvest_constant(self):
        self.assertIn("__wr_locks__", HARVEST_LOG_SCRIPT)


class TestParse(unittest.TestCase):

    def test_basic(self):
        events = parse_log([
            {"id": "1", "name": "cart", "outcome": "acquired", "time": 5},
            {"id": "1", "name": "cart", "outcome": "released", "time": 12},
        ])
        self.assertEqual([e.outcome for e in events],
                         [LockOutcome.ACQUIRED, LockOutcome.RELEASED])

    def test_filters_requested(self):
        events = parse_log([
            {"id": "1", "name": "x", "outcome": "requested", "time": 0},
            {"id": "1", "name": "x", "outcome": "acquired", "time": 1},
        ])
        self.assertEqual(len(events), 1)

    def test_skips_unknown_outcome(self):
        events = parse_log([{"id": "x", "name": "y", "outcome": "weird"}])
        self.assertEqual(events, [])

    def test_skips_non_dict(self):
        events = parse_log(["str", None])
        self.assertEqual(events, [])

    def test_rejects_non_list(self):
        with self.assertRaises(WebLocksError):
            parse_log({"x": 1})


class TestAssertNoDeadlock(unittest.TestCase):

    def test_pass(self):
        events = parse_log([
            {"id": "1", "name": "x", "outcome": "acquired"},
            {"id": "1", "name": "x", "outcome": "released"},
        ])
        assert_no_deadlock(events)

    def test_unmatched(self):
        events = parse_log([
            {"id": "1", "name": "x", "outcome": "acquired"},
        ])
        with self.assertRaises(WebLocksError):
            assert_no_deadlock(events)


class TestAssertSerialised(unittest.TestCase):

    def test_pass(self):
        events = parse_log([
            {"id": "1", "name": "x", "outcome": "acquired"},
            {"id": "1", "name": "x", "outcome": "released"},
            {"id": "2", "name": "x", "outcome": "acquired"},
            {"id": "2", "name": "x", "outcome": "released"},
        ])
        assert_serialised(events, name="x")

    def test_overlap_fails(self):
        events = parse_log([
            {"id": "1", "name": "x", "outcome": "acquired"},
            {"id": "2", "name": "x", "outcome": "acquired"},
        ])
        with self.assertRaises(WebLocksError):
            assert_serialised(events, name="x")

    def test_other_name_ignored(self):
        events = parse_log([
            {"id": "1", "name": "x", "outcome": "acquired"},
            {"id": "2", "name": "y", "outcome": "acquired"},
        ])
        assert_serialised(events, name="x")


class TestAssertIfAvailable(unittest.TestCase):

    def test_pass(self):
        events = parse_log([
            {"id": "1", "name": "x", "outcome": "unavailable", "if_available": True},
        ])
        assert_if_available_unavailable(events, name="x")

    def test_no_match(self):
        with self.assertRaises(WebLocksError):
            assert_if_available_unavailable([], name="x")


class TestAssertAcquiredCount(unittest.TestCase):

    def test_pass(self):
        events = parse_log([
            {"id": "1", "name": "x", "outcome": "acquired"},
            {"id": "2", "name": "x", "outcome": "acquired"},
        ])
        assert_acquired_count(events, name="x", expected=2)

    def test_fail(self):
        with self.assertRaises(WebLocksError):
            assert_acquired_count([], name="x", expected=1)


if __name__ == "__main__":
    unittest.main()
