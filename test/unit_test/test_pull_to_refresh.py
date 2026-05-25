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
        with self.assertRaises(PullToRefreshError):
            assert_overscroll_contained(PullToRefreshSnapshot(overscroll_y="auto"))


class TestThreshold(unittest.TestCase):

    def test_pass(self):
        assert_threshold_sensible(PullToRefreshSnapshot(pull_threshold_px=80))

    def test_too_low(self):
        with self.assertRaises(PullToRefreshError):
            assert_threshold_sensible(PullToRefreshSnapshot(pull_threshold_px=10))

    def test_too_high(self):
        with self.assertRaises(PullToRefreshError):
            assert_threshold_sensible(PullToRefreshSnapshot(pull_threshold_px=500))

    def test_missing(self):
        with self.assertRaises(PullToRefreshError):
            assert_threshold_sensible(PullToRefreshSnapshot())

    def test_bad_bounds(self):
        with self.assertRaises(PullToRefreshError):
            assert_threshold_sensible(
                PullToRefreshSnapshot(pull_threshold_px=10),
                min_px=0, max_px=10,
            )


class TestRefreshEvent(unittest.TestCase):

    def test_pass(self):
        assert_refresh_triggered(RefreshEvent(fired=True,
                                              network_refetched=True))

    def test_no_handler(self):
        with self.assertRaises(PullToRefreshError):
            assert_refresh_triggered(RefreshEvent())

    def test_no_network(self):
        with self.assertRaises(PullToRefreshError):
            assert_refresh_triggered(RefreshEvent(fired=True))


if __name__ == "__main__":
    unittest.main()
