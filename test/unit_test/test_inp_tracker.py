"""Unit tests for je_web_runner.utils.inp_tracker."""
import unittest

from je_web_runner.utils.inp_tracker.tracker import (
    HARVEST_SCRIPT,
    InpRating,
    InpReport,
    InpTrackerError,
    InteractionEvent,
    assert_inp_under,
    assert_no_poor_interactions,
    build_install_script,
    parse_log,
)


def _raw(duration, iid=1, name="click"):
    return {
        "name": name, "interactionId": iid, "duration_ms": duration,
        "startTime": 0, "processingStart": 0, "processingEnd": 0,
        "targetTag": "BUTTON",
    }


class TestScripts(unittest.TestCase):

    def test_install_guard(self):
        js = build_install_script()
        self.assertIn("__wr_inp_installed__", js)
        self.assertIn("PerformanceObserver", js)

    def test_harvest_constant(self):
        self.assertIn("__wr_inp_log__", HARVEST_SCRIPT)


class TestParseLog(unittest.TestCase):

    def test_basic(self):
        events = parse_log([_raw(120), _raw(300, iid=2)])
        self.assertEqual(len(events), 2)
        self.assertEqual(events[1].interaction_id, 2)

    def test_skips_non_dict(self):
        self.assertEqual(parse_log(["x", None]), [])  # type: ignore[list-item]

    def test_skips_bad_duration(self):
        out = parse_log([{"duration_ms": "not a number"}])
        self.assertEqual(out, [])

    def test_skips_negative_duration(self):
        out = parse_log([_raw(-1)])
        self.assertEqual(out, [])

    def test_rejects_non_list_payload(self):
        with self.assertRaises(InpTrackerError):
            parse_log("nope")  # type: ignore[arg-type]


class TestInpReport(unittest.TestCase):

    def test_inp_uses_worst_when_few(self):
        report = InpReport(events=parse_log([_raw(120), _raw(300), _raw(450)]))
        self.assertEqual(report.inp(), 450)
        self.assertEqual(report.rating(), InpRating.NEEDS_WORK)

    def test_inp_uses_p98_when_many(self):
        events = parse_log([_raw(50, iid=i) for i in range(1, 51)])
        report = InpReport(events=events)
        self.assertEqual(report.inp(), 50)
        self.assertEqual(report.rating(), InpRating.GOOD)

    def test_no_events_inp_none(self):
        self.assertIsNone(InpReport().inp())
        self.assertEqual(InpReport().rating(), InpRating.GOOD)

    def test_filtered_drops_zero_id(self):
        events = [InteractionEvent(name="x", interaction_id=0, duration_ms=10),
                  InteractionEvent(name="y", interaction_id=1, duration_ms=10)]
        self.assertEqual(len(InpReport(events=events).filtered()), 1)

    def test_percentile(self):
        report = InpReport(events=parse_log([
            _raw(d, iid=i) for i, d in enumerate([10, 20, 30, 40], start=1)
        ]))
        self.assertEqual(report.percentile(50), 30)
        self.assertEqual(report.percentile(100), 40)

    def test_percentile_bad_input(self):
        with self.assertRaises(InpTrackerError):
            InpReport().percentile(-1)
        with self.assertRaises(InpTrackerError):
            InpReport().percentile(150)


class TestAssertInpUnder(unittest.TestCase):

    def test_pass(self):
        assert_inp_under(
            InpReport(events=parse_log([_raw(100), _raw(150)])),
            max_ms=200,
        )

    def test_fail(self):
        with self.assertRaises(InpTrackerError):
            assert_inp_under(
                InpReport(events=parse_log([_raw(300)])),
                max_ms=200,
            )

    def test_empty_passes(self):
        assert_inp_under(InpReport(), max_ms=100)

    def test_bad_budget(self):
        with self.assertRaises(InpTrackerError):
            assert_inp_under(InpReport(), max_ms=0)

    def test_rejects_non_report(self):
        with self.assertRaises(InpTrackerError):
            assert_inp_under("nope", max_ms=100)  # type: ignore[arg-type]


class TestAssertNoPoor(unittest.TestCase):

    def test_pass(self):
        assert_no_poor_interactions(
            InpReport(events=parse_log([_raw(100), _raw(450)])),
        )

    def test_fail(self):
        with self.assertRaises(InpTrackerError):
            assert_no_poor_interactions(
                InpReport(events=parse_log([_raw(600)])),
            )

    def test_rejects_non_report(self):
        with self.assertRaises(InpTrackerError):
            assert_no_poor_interactions("nope")  # type: ignore[arg-type]


class TestEventRating(unittest.TestCase):

    def test_ratings(self):
        self.assertEqual(InteractionEvent("x", 1, 100).rating(), InpRating.GOOD)
        self.assertEqual(InteractionEvent("x", 1, 250).rating(), InpRating.NEEDS_WORK)
        self.assertEqual(InteractionEvent("x", 1, 600).rating(), InpRating.POOR)

    def test_to_dict_includes_rating(self):
        d = InteractionEvent("x", 1, 100).to_dict()
        self.assertEqual(d["rating"], "good")


if __name__ == "__main__":
    unittest.main()
