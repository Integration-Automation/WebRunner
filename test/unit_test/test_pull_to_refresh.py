"""Unit tests for je_web_runner.utils.pull_to_refresh."""
import unittest

from je_web_runner.utils.pull_to_refresh.refresh import (
    HARVEST_SCRIPT,
    PullToRefreshError,
    PullToRefreshSnapshot,
    RefreshEvent,
    assert_overscroll_contained,
    assert_refresh_triggered,
    assert_threshold_sensible,
    parse_snapshot,
)


class TestScript(unittest.TestCase):

    def test_contains(self):
        self.assertIn("overscrollBehaviorY", HARVEST_SCRIPT)


class TestParse(unittest.TestCase):

    def test_basic(self):
        snap = parse_snapshot({"overscroll_y": "contain",
                               "pull_threshold_attr": "80"})
        self.assertEqual(snap.pull_threshold_px, 80)

    def test_bad(self):
        with self.assertRaises(PullToRefreshError):
            parse_snapshot("nope")

    def test_non_numeric_threshold(self):
        with self.assertRaises(PullToRefreshError):
            parse_snapshot({"pull_threshold_attr": "loose"})


class TestOverscroll(unittest.TestCase):

    def test_pass(self):
        assert_overscroll_contained(PullToRefreshSnapshot(overscroll_y="contain"))

    def test_fail(self):
        pull_to_refresh_snapshot = PullToRefreshSnapshot(overscroll_y="auto")
        with self.assertRaises(PullToRefreshError):
            assert_overscroll_contained(pull_to_refresh_snapshot)


class TestThreshold(unittest.TestCase):

    def test_pass(self):
        assert_threshold_sensible(PullToRefreshSnapshot(pull_threshold_px=80))

    def test_too_low(self):
        pull_to_refresh_snapshot = PullToRefreshSnapshot(pull_threshold_px=10)
        with self.assertRaises(PullToRefreshError):
            assert_threshold_sensible(pull_to_refresh_snapshot)

    def test_too_high(self):
        pull_to_refresh_snapshot = PullToRefreshSnapshot(pull_threshold_px=500)
        with self.assertRaises(PullToRefreshError):
            assert_threshold_sensible(pull_to_refresh_snapshot)

    def test_missing(self):
        pull_to_refresh_snapshot = PullToRefreshSnapshot()
        with self.assertRaises(PullToRefreshError):
            assert_threshold_sensible(pull_to_refresh_snapshot)

    def test_bad_bounds(self):
        pull_to_refresh_snapshot = PullToRefreshSnapshot(pull_threshold_px=10)
        with self.assertRaises(PullToRefreshError):
            assert_threshold_sensible(
                pull_to_refresh_snapshot,
                min_px=0, max_px=10,
            )


class TestRefreshEvent(unittest.TestCase):

    def test_pass(self):
        assert_refresh_triggered(RefreshEvent(fired=True,
                                              network_refetched=True))

    def test_no_handler(self):
        refresh_event = RefreshEvent()
        with self.assertRaises(PullToRefreshError):
            assert_refresh_triggered(refresh_event)

    def test_no_network(self):
        refresh_event = RefreshEvent(fired=True)
        with self.assertRaises(PullToRefreshError):
            assert_refresh_triggered(refresh_event)


if __name__ == "__main__":
    unittest.main()
