"""Unit tests for je_web_runner.utils.view_transitions."""
import unittest

from je_web_runner.utils.view_transitions.transitions import (
    TransitionRun,
    ViewTransitionsError,
    assert_all_finished,
    assert_cls_under,
    assert_group_present,
    assert_under_duration,
    build_instrumentation_script,
    parse_log,
)


class TestInstrumentation(unittest.TestCase):

    def test_script_contains_install_guard(self):
        js = build_instrumentation_script()
        self.assertIn("__wr_vt_installed__", js)
        self.assertIn("startViewTransition", js)


class TestParseLog(unittest.TestCase):

    def test_parses_basic(self):
        runs = parse_log([{
            "id": "vt_1", "startedAt": 100.0, "finishedAt": 350.0,
            "durationMs": 250.0, "error": None,
            "layoutShifts": 0.02, "maxShiftValue": 0.01,
            "groups": ["header"],
        }])
        self.assertEqual(len(runs), 1)
        self.assertTrue(runs[0].is_finished())
        self.assertEqual(runs[0].groups, ["header"])

    def test_error_marked_not_finished(self):
        runs = parse_log([{
            "id": "vt_1", "startedAt": 0, "finishedAt": 10,
            "durationMs": 10, "error": "AbortError",
        }])
        self.assertFalse(runs[0].is_finished())

    def test_ignores_non_dict(self):
        runs = parse_log(["not dict", None])  # type: ignore[list-item]
        self.assertEqual(runs, [])

    def test_rejects_non_list(self):
        with self.assertRaises(ViewTransitionsError):
            parse_log("nope")  # type: ignore[arg-type]


class TestAssertFinished(unittest.TestCase):

    def test_pass(self):
        runs = parse_log([{"id": "a", "startedAt": 0, "finishedAt": 1, "durationMs": 1}])
        assert_all_finished(runs)

    def test_empty_rejected(self):
        with self.assertRaises(ViewTransitionsError):
            assert_all_finished([])

    def test_fail_with_error(self):
        runs = parse_log([{
            "id": "a", "startedAt": 0, "finishedAt": 1, "durationMs": 1,
            "error": "boom",
        }])
        with self.assertRaises(ViewTransitionsError):
            assert_all_finished(runs)

    def test_fail_unfinished(self):
        runs = parse_log([{"id": "a", "startedAt": 0}])
        with self.assertRaises(ViewTransitionsError):
            assert_all_finished(runs)


class TestAssertDuration(unittest.TestCase):

    def test_pass(self):
        runs = parse_log([{
            "id": "a", "startedAt": 0, "finishedAt": 100, "durationMs": 100,
        }])
        assert_under_duration(runs, max_duration_ms=200)

    def test_fail(self):
        runs = parse_log([{
            "id": "a", "startedAt": 0, "finishedAt": 300, "durationMs": 300,
        }])
        with self.assertRaises(ViewTransitionsError):
            assert_under_duration(runs, max_duration_ms=200)

    def test_bad_threshold(self):
        with self.assertRaises(ViewTransitionsError):
            assert_under_duration([], max_duration_ms=0)


class TestAssertCls(unittest.TestCase):

    def test_pass(self):
        runs = parse_log([{
            "id": "a", "startedAt": 0, "finishedAt": 1, "durationMs": 1,
            "layoutShifts": 0.05, "maxShiftValue": 0.02,
        }])
        assert_cls_under(runs)

    def test_fail_cumulative(self):
        runs = parse_log([{
            "id": "a", "startedAt": 0, "finishedAt": 1, "durationMs": 1,
            "layoutShifts": 0.5, "maxShiftValue": 0.02,
        }])
        with self.assertRaises(ViewTransitionsError):
            assert_cls_under(runs)

    def test_fail_single(self):
        runs = parse_log([{
            "id": "a", "startedAt": 0, "finishedAt": 1, "durationMs": 1,
            "layoutShifts": 0.05, "maxShiftValue": 0.5,
        }])
        with self.assertRaises(ViewTransitionsError):
            assert_cls_under(runs)

    def test_bad_threshold(self):
        with self.assertRaises(ViewTransitionsError):
            assert_cls_under([], max_cls=-1)


class TestAssertGroup(unittest.TestCase):

    def test_pass(self):
        runs = [TransitionRun(id="a", started_at=0, groups=["root", "nav"])]
        assert_group_present(runs, "nav")

    def test_fail(self):
        runs = [TransitionRun(id="a", started_at=0, groups=["root"])]
        with self.assertRaises(ViewTransitionsError):
            assert_group_present(runs, "nav")

    def test_empty_name(self):
        with self.assertRaises(ViewTransitionsError):
            assert_group_present([], "")


if __name__ == "__main__":
    unittest.main()
