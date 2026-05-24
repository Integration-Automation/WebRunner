"""Unit tests for je_web_runner.utils.long_animation_frame."""
import unittest

from je_web_runner.utils.long_animation_frame.frames import (
    HARVEST_SCRIPT,
    LoafReport,
    LongAnimationFrameError,
    assert_no_frame_over,
    assert_total_blocking_under,
    build_install_script,
    parse_log,
)


def _frame(duration=100, blocking=80, scripts=None):
    return {
        "duration_ms": duration,
        "render_start_ms": 10,
        "style_layout_start_ms": 20,
        "start_time_ms": 0,
        "blocking_duration_ms": blocking,
        "scripts": scripts or [],
    }


def _script(name, duration=50, source_url=""):
    return {
        "name": name, "invoker": "click", "invoker_type": "event-listener",
        "source_url": source_url or f"https://x/{name}.js",
        "duration_ms": duration,
        "forced_style_layout_duration_ms": 5,
        "pause_duration_ms": 0,
    }


class TestScripts(unittest.TestCase):

    def test_install_guard(self):
        js = build_install_script()
        self.assertIn("__wr_loaf_installed__", js)
        self.assertIn("long-animation-frame", js)

    def test_harvest_constant(self):
        self.assertIn("__wr_loaf_log__", HARVEST_SCRIPT)


class TestParseLog(unittest.TestCase):

    def test_basic(self):
        frames = parse_log([_frame(150, 100, [_script("react", 50)])])
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0].duration_ms, 150)
        self.assertEqual(len(frames[0].scripts), 1)
        self.assertEqual(frames[0].scripts[0].name, "react")

    def test_skips_non_dict_frame(self):
        self.assertEqual(parse_log(["string", None]), [])  # type: ignore[list-item]

    def test_skips_non_dict_script(self):
        frames = parse_log([_frame(100, 80, ["not dict"])])
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0].scripts, [])

    def test_rejects_non_list(self):
        with self.assertRaises(LongAnimationFrameError):
            parse_log({"x": 1})  # type: ignore[arg-type]


class TestReport(unittest.TestCase):

    def test_worst_frame(self):
        report = LoafReport(frames=parse_log([
            _frame(100), _frame(200), _frame(50),
        ]))
        self.assertEqual(report.worst_frame_ms(), 200)

    def test_worst_frame_empty(self):
        self.assertEqual(LoafReport().worst_frame_ms(), 0.0)

    def test_total_blocking(self):
        report = LoafReport(frames=parse_log([
            _frame(100, blocking=60), _frame(100, blocking=40),
        ]))
        self.assertEqual(report.total_blocking_ms(), 100)

    def test_top_scripts_aggregates_by_url(self):
        report = LoafReport(frames=parse_log([
            _frame(scripts=[_script("a", 50, "https://x/a.js")]),
            _frame(scripts=[_script("a-dup", 30, "https://x/a.js"),
                            _script("b", 100, "https://x/b.js")]),
        ]))
        top = report.top_scripts(n=2)
        self.assertEqual(top[0].source_url, "https://x/b.js")
        self.assertEqual(top[0].duration_ms, 100)
        # Aggregated 'a' script: 50 + 30 = 80
        self.assertEqual(top[1].source_url, "https://x/a.js")
        self.assertEqual(top[1].duration_ms, 80)


class TestAssertions(unittest.TestCase):

    def test_no_frame_over_pass(self):
        report = LoafReport(frames=parse_log([_frame(40)]))
        assert_no_frame_over(report, max_ms=50)

    def test_no_frame_over_fail(self):
        report = LoafReport(frames=parse_log([_frame(80)]))
        with self.assertRaises(LongAnimationFrameError):
            assert_no_frame_over(report, max_ms=50)

    def test_no_frame_over_bad_threshold(self):
        with self.assertRaises(LongAnimationFrameError):
            assert_no_frame_over(LoafReport(), max_ms=0)

    def test_no_frame_over_rejects_non_report(self):
        with self.assertRaises(LongAnimationFrameError):
            assert_no_frame_over("nope", max_ms=50)  # type: ignore[arg-type]

    def test_total_blocking_pass(self):
        report = LoafReport(frames=parse_log([_frame(blocking=50)]))
        assert_total_blocking_under(report, max_ms=100)

    def test_total_blocking_fail(self):
        report = LoafReport(frames=parse_log([_frame(blocking=200)]))
        with self.assertRaises(LongAnimationFrameError):
            assert_total_blocking_under(report, max_ms=100)

    def test_total_blocking_bad_threshold(self):
        with self.assertRaises(LongAnimationFrameError):
            assert_total_blocking_under(LoafReport(), max_ms=-1)

    def test_total_blocking_rejects_non_report(self):
        with self.assertRaises(LongAnimationFrameError):
            assert_total_blocking_under("nope", max_ms=50)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
