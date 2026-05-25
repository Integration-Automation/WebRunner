"""Unit tests for je_web_runner.utils.hydration_streaming."""
import unittest

from je_web_runner.utils.hydration_streaming.timing import (
    BoundaryTiming,
    HARVEST_SCRIPT,
    HydrationStreamingError,
    INSTALL_SCRIPT,
    StreamingReport,
    assert_all_arrived,
    assert_arrival_under,
    assert_interactive_under,
    assert_order,
    parse_log,
)


def _payload(boundaries):
    return {"boundaries": boundaries, "start": 0}


class TestScripts(unittest.TestCase):

    def test_install_guard(self):
        self.assertIn("__wr_hs_installed__", INSTALL_SCRIPT)
        self.assertIn("MutationObserver", INSTALL_SCRIPT)

    def test_harvest_constant(self):
        self.assertIn("__wr_hs__", HARVEST_SCRIPT)


class TestParse(unittest.TestCase):

    def test_basic(self):
        rep = parse_log(_payload({
            "B:1": {"placeholder": 10, "arrived": 50, "interactive": 70},
        }))
        b = rep.boundaries[0]
        self.assertEqual(b.id, "B:1")
        self.assertEqual(b.time_to_arrival(), 40)
        self.assertEqual(b.time_to_interactive(), 20)

    def test_skips_non_dict(self):
        rep = parse_log(_payload({"x": "not a dict"}))
        self.assertEqual(rep.boundaries, [])

    def test_rejects_non_dict_payload(self):
        with self.assertRaises(HydrationStreamingError):
            parse_log("nope")

    def test_rejects_bad_boundaries(self):
        with self.assertRaises(HydrationStreamingError):
            parse_log({"boundaries": "x"})

    def test_handles_bad_timing(self):
        rep = parse_log(_payload({"x": {"placeholder": "abc"}}))
        self.assertIsNone(rep.boundaries[0].placeholder_ms)


class TestAssertAllArrived(unittest.TestCase):

    def test_pass(self):
        assert_all_arrived(parse_log(_payload({"x": {"arrived": 5}})))

    def test_fail(self):
        with self.assertRaises(HydrationStreamingError):
            assert_all_arrived(parse_log(_payload({"x": {"placeholder": 5}})))


class TestAssertArrivalUnder(unittest.TestCase):

    def test_pass(self):
        rep = parse_log(_payload({"x": {"placeholder": 0, "arrived": 100}}))
        self.assertEqual(assert_arrival_under(rep, id_="x", max_ms=200), 100)

    def test_too_slow(self):
        rep = parse_log(_payload({"x": {"placeholder": 0, "arrived": 500}}))
        with self.assertRaises(HydrationStreamingError):
            assert_arrival_under(rep, id_="x", max_ms=200)

    def test_missing_timing(self):
        rep = parse_log(_payload({"x": {"placeholder": 0}}))
        with self.assertRaises(HydrationStreamingError):
            assert_arrival_under(rep, id_="x", max_ms=200)

    def test_unknown(self):
        with self.assertRaises(HydrationStreamingError):
            assert_arrival_under(StreamingReport(), id_="x", max_ms=200)

    def test_bad_threshold(self):
        with self.assertRaises(HydrationStreamingError):
            assert_arrival_under(StreamingReport(), id_="x", max_ms=0)


class TestAssertInteractiveUnder(unittest.TestCase):

    def test_pass(self):
        rep = parse_log(_payload({"x": {"arrived": 100, "interactive": 200}}))
        self.assertEqual(assert_interactive_under(rep, id_="x", max_ms=200), 100)

    def test_too_slow(self):
        rep = parse_log(_payload({"x": {"arrived": 100, "interactive": 1000}}))
        with self.assertRaises(HydrationStreamingError):
            assert_interactive_under(rep, id_="x", max_ms=200)

    def test_missing_timing(self):
        with self.assertRaises(HydrationStreamingError):
            assert_interactive_under(
                parse_log(_payload({"x": {"arrived": 100}})),
                id_="x", max_ms=200,
            )

    def test_unknown_boundary(self):
        with self.assertRaises(HydrationStreamingError):
            assert_interactive_under(StreamingReport(), id_="x", max_ms=200)

    def test_bad_threshold(self):
        with self.assertRaises(HydrationStreamingError):
            assert_interactive_under(StreamingReport(), id_="x", max_ms=-1)


class TestAssertOrder(unittest.TestCase):

    def test_pass(self):
        rep = parse_log(_payload({
            "a": {"arrived": 10},
            "b": {"arrived": 20},
            "c": {"arrived": 30},
        }))
        assert_order(rep, expected_order=["a", "b", "c"])

    def test_wrong_order(self):
        rep = parse_log(_payload({
            "a": {"arrived": 30},
            "b": {"arrived": 10},
        }))
        with self.assertRaises(HydrationStreamingError):
            assert_order(rep, expected_order=["a", "b"])

    def test_empty_expected(self):
        with self.assertRaises(HydrationStreamingError):
            assert_order(StreamingReport(), expected_order=[])

    def test_ignores_extras(self):
        rep = parse_log(_payload({
            "a": {"arrived": 10},
            "b": {"arrived": 20},
            "c": {"arrived": 30},
        }))
        assert_order(rep, expected_order=["a", "b"])


class TestByIdLookup(unittest.TestCase):

    def test_by_id(self):
        rep = StreamingReport(boundaries=[BoundaryTiming(id="x")])
        self.assertIn("x", rep.by_id())


if __name__ == "__main__":
    unittest.main()
