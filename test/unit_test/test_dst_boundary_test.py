"""Unit tests for je_web_runner.utils.dst_boundary_test."""
import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from je_web_runner.utils.dst_boundary_test.boundary import (
    DstBoundaryError,
    Transition,
    assert_fired_around,
    assert_no_duplicate_fires,
    expected_fires_around_boundary,
    find_boundaries,
    is_ambiguous_local_time,
    is_nonexistent_local_time,
)


class TestFindBoundaries(unittest.TestCase):

    def test_us_eastern_2024(self):
        boundaries = find_boundaries("America/New_York", 2024, 2024)
        kinds = {b.transition for b in boundaries}
        self.assertIn(Transition.SPRING_FORWARD, kinds)
        self.assertIn(Transition.FALL_BACK, kinds)

    def test_no_dst_zone(self):
        # Phoenix doesn't observe DST
        boundaries = find_boundaries("America/Phoenix", 2024, 2024)
        self.assertEqual(boundaries, [])

    def test_bad_tz(self):
        with self.assertRaises(DstBoundaryError):
            find_boundaries("Mars/Olympus", 2024, 2024)

    def test_bad_year_order(self):
        with self.assertRaises(DstBoundaryError):
            find_boundaries("UTC", 2024, 2020)

    def test_range_too_large(self):
        with self.assertRaises(DstBoundaryError):
            find_boundaries("UTC", 2000, 2025)

    def test_empty_tz(self):
        with self.assertRaises(DstBoundaryError):
            find_boundaries("", 2024, 2024)


class TestNonexistent(unittest.TestCase):

    def test_spring_forward_gap(self):
        # In US Eastern 2024, 2:30am on Mar 10 doesn't exist
        gap = datetime(2024, 3, 10, 2, 30)
        self.assertTrue(is_nonexistent_local_time("America/New_York", gap))

    def test_normal_time_exists(self):
        ok = datetime(2024, 6, 1, 12, 0)
        self.assertFalse(is_nonexistent_local_time("America/New_York", ok))

    def test_rejects_tz_aware(self):
        with self.assertRaises(DstBoundaryError):
            is_nonexistent_local_time(
                "America/New_York",
                datetime(2024, 6, 1, tzinfo=ZoneInfo("UTC")),
            )


class TestAmbiguous(unittest.TestCase):

    def test_fall_back_overlap(self):
        # In US Eastern 2024, 1:30am on Nov 3 happens twice
        overlap = datetime(2024, 11, 3, 1, 30)
        self.assertTrue(is_ambiguous_local_time("America/New_York", overlap))

    def test_normal_time_unambiguous(self):
        ok = datetime(2024, 6, 1, 12, 0)
        self.assertFalse(is_ambiguous_local_time("America/New_York", ok))

    def test_rejects_tz_aware(self):
        with self.assertRaises(DstBoundaryError):
            is_ambiguous_local_time(
                "UTC", datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")),
            )


class TestExpectedFires(unittest.TestCase):

    def test_spring_no_fire(self):
        boundaries = find_boundaries("America/New_York", 2024, 2024)
        spring = next(b for b in boundaries
                      if b.transition == Transition.SPRING_FORWARD)
        self.assertEqual(expected_fires_around_boundary(spring), [])

    def test_fall_back_two_fires(self):
        boundaries = find_boundaries("America/New_York", 2024, 2024)
        fall = next(b for b in boundaries
                    if b.transition == Transition.FALL_BACK)
        # at 01:30 local, fall-back makes that wall-clock happen twice
        fires = expected_fires_around_boundary(fall, wall_clock_hour=1,
                                               wall_clock_minute=30)
        self.assertEqual(len(fires), 2)
        self.assertNotEqual(fires[0].moment_utc, fires[1].moment_utc)

    def test_bad_hour(self):
        boundaries = find_boundaries("America/New_York", 2024, 2024)
        with self.assertRaises(DstBoundaryError):
            expected_fires_around_boundary(boundaries[0], wall_clock_hour=99)


class TestAssertDup(unittest.TestCase):

    def test_pass(self):
        utc = ZoneInfo("UTC")
        assert_no_duplicate_fires([
            datetime(2024, 1, 1, 12, tzinfo=utc),
            datetime(2024, 1, 2, 12, tzinfo=utc),
        ])

    def test_fail(self):
        utc = ZoneInfo("UTC")
        with self.assertRaises(DstBoundaryError):
            assert_no_duplicate_fires([
                datetime(2024, 1, 1, 12, tzinfo=utc),
                datetime(2024, 1, 1, 12, tzinfo=utc),
            ])

    def test_naive_rejected(self):
        with self.assertRaises(DstBoundaryError):
            assert_no_duplicate_fires([datetime(2024, 1, 1)])


class TestAssertFired(unittest.TestCase):

    def test_pass(self):
        utc = ZoneInfo("UTC")
        assert_fired_around(
            [datetime(2024, 1, 1, 12, 0, 30, tzinfo=utc)],
            expected_utc=datetime(2024, 1, 1, 12, 0, tzinfo=utc),
        )

    def test_fail(self):
        utc = ZoneInfo("UTC")
        with self.assertRaises(DstBoundaryError):
            assert_fired_around(
                [datetime(2024, 1, 1, 13, tzinfo=utc)],
                expected_utc=datetime(2024, 1, 1, 12, tzinfo=utc),
            )

    def test_rejects_naive_expected(self):
        with self.assertRaises(DstBoundaryError):
            assert_fired_around([], datetime(2024, 1, 1))


if __name__ == "__main__":
    unittest.main()
