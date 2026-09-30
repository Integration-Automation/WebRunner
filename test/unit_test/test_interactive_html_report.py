"""The self-contained interactive HTML report: timeline, screenshots, diffs, waterfall, axe badges."""
import base64
import json
import os
import tempfile
import unittest
from pathlib import Path

from je_web_runner.utils.exception.exceptions import WebRunnerHTMLException
from je_web_runner.utils.executor.action_executor import executor
from je_web_runner.utils.generate_report.interactive_html_report import (
    generate_interactive_html,
    generate_interactive_html_report,
)
from je_web_runner.utils.test_record.test_record_class import test_record_instance

_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
_RECORDS = [
    {"function_name": "to_url", "local_param": {"url": "https://x.test/"}, "time": "2026-10-01 10:00:00.000000",
     "program_exception": "None"},
    {"function_name": "check_title", "local_param": {"title": "<b>Home</b>"}, "time": "2026-10-01 10:00:05.000000",
     "program_exception": "AssertionError(\"title: 'Home' != 'Hone'\")"},
]
_HAR = {"log": {"version": "1.2", "entries": [
    {"startedDateTime": "2026-10-01T10:00:00.000Z", "time": 120, "request": {"method": "GET", "url": "https://x.test/"},
     "response": {"status": 200}},
    {"startedDateTime": "2026-10-01T10:00:00.100Z", "time": 80,
     "request": {"method": "POST", "url": "https://x.test/api?<script>"}, "response": {"status": 500}},
]}}
_AXE = {"violations": [
    {"id": "color-contrast", "impact": "serious", "help": "Elements must have sufficient contrast",
     "nodes": [{"target": ["#footer"]}]},
    {"id": "image-alt", "impact": "critical", "help": "Images must have alternate text", "nodes": []},
]}


class TestInteractiveReport(unittest.TestCase):

    def setUp(self):
        self.previous = (test_record_instance.test_record_list, test_record_instance.init_record)
        test_record_instance.test_record_list = [dict(record) for record in _RECORDS]
        self.addCleanup(self._restore)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)

    def _restore(self):
        test_record_instance.test_record_list, test_record_instance.init_record = self.previous

    def test_timeline_escapes_and_opens_failures(self):
        page = generate_interactive_html()
        self.assertIn("2 steps", page)
        self.assertIn("1 failed", page)
        self.assertIn("&lt;b&gt;Home&lt;/b&gt;", page)
        self.assertNotIn("<b>Home</b>", page)
        self.assertIn("<details class='step-fail' open>", page)
        self.assertNotIn("<script", page.lower())

    def test_an_assertion_comparison_shows_a_diff(self):
        page = generate_interactive_html()
        self.assertIn("<span class='diff-del'>-&#x27;Home&#x27;</span>", page)
        self.assertIn("<span class='diff-add'>+&#x27;Hone&#x27;</span>", page)

    def test_screenshots_are_embedded_under_the_step_they_follow(self):
        shots = self.tmp / "shots"
        shots.mkdir()
        (shots / "20261001_100006_000000_WR_check_title.png").write_bytes(_PNG)
        early = shots / "early.png"
        early.write_bytes(_PNG)
        stamp = 1_000_000_000  # 2001: before every step
        os.utime(early, (stamp, stamp))
        (shots / "notes.txt").write_text("not an image", encoding="utf-8")
        page = generate_interactive_html(screenshot_dir=str(shots))
        self.assertEqual(page.count("data:image/png;base64,"), 2)
        failed_step = page.index("check_title")
        self.assertGreater(page.index("20261001_100006_000000_WR_check_title.png"), failed_step)
        self.assertLess(page.index("early.png"), page.index("#1 "))
        self.assertIn("Screenshots before the first step", page)

    def test_network_waterfall_from_a_har_file(self):
        har = self.tmp / "run.har"
        har.write_text(json.dumps(_HAR), encoding="utf-8")
        page = generate_interactive_html(har_path=str(har))
        self.assertIn("2 requests over 180 ms", page)
        self.assertIn("class='bar err'", page)
        self.assertIn("left:55.56%", page)  # the second request starts 100 ms into a 180 ms span
        self.assertIn("api?&lt;script&gt;", page)

    def test_axe_badges_from_a_dict_or_a_file(self):
        page = generate_interactive_html(a11y_results=_AXE)
        self.assertIn("<span class='badge critical'>critical: 1</span>", page)
        self.assertIn("<span class='badge serious'>serious: 1</span>", page)
        self.assertIn("color-contrast", page)
        axe_file = self.tmp / "axe.json"
        axe_file.write_text(json.dumps(_AXE), encoding="utf-8")
        self.assertIn("image-alt", generate_interactive_html(a11y_results=str(axe_file)))

    def test_bad_inputs_raise(self):
        with self.assertRaises(WebRunnerHTMLException):
            generate_interactive_html(screenshot_dir=str(self.tmp / "missing"))
        (self.tmp / "bad.har").write_text("{}", encoding="utf-8")
        with self.assertRaises(WebRunnerHTMLException):
            generate_interactive_html(har_path=str(self.tmp / "bad.har"))
        with self.assertRaises(WebRunnerHTMLException):
            generate_interactive_html(a11y_results={"passes": []})
        test_record_instance.test_record_list = []
        with self.assertRaises(WebRunnerHTMLException):
            generate_interactive_html()

    def test_writes_the_file_through_the_action_executor(self):
        target = self.tmp / "out" / "report"
        record, failed = executor.collect_action_results(
            [["WR_generate_interactive_html_report", {"html_name": str(target)}]])
        self.assertEqual(failed, [])
        self.assertTrue((self.tmp / "out" / "report.html").is_file())
        self.assertEqual(generate_interactive_html_report(str(target)), str(target) + ".html")


if __name__ == "__main__":
    unittest.main()
