import os
import tempfile
import unittest
from pathlib import Path

from je_web_runner.utils.replay_studio.replay_studio import (
    build_replay_html,
    export_replay_studio,
)
from je_web_runner.utils.test_record.test_record_class import (
    record_action_to_list,
    test_record_instance,
)


class TestBuildReplayHtml(unittest.TestCase):

    def setUp(self):
        test_record_instance.clean_record()
        self._original = test_record_instance.init_record
        test_record_instance.init_record = True

    def tearDown(self):
        test_record_instance.clean_record()
        test_record_instance.init_record = self._original

    def test_html_contains_records(self):
        record_action_to_list("step_ok", {"a": 1}, None)
        record_action_to_list("step_fail", None, RuntimeError("boom"))
        html_content = build_replay_html()
        self.assertIn("step_ok", html_content)
        self.assertIn("step_fail", html_content)
        self.assertIn("PASSED", html_content)
        self.assertIn("FAILED", html_content)
        self.assertIn("RuntimeError", html_content)

    def test_screenshot_dir_links_matching_image(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            shot = os.path.join(tmpdir, "20260425_step_fail.png")
            Path(shot).write_bytes(b"\x89PNG\r\n\x1a\n")
            record_action_to_list("step_fail", None, RuntimeError("boom"))
            html_content = build_replay_html(screenshot_dir=tmpdir)
            self.assertIn("step_fail.png", html_content)
            self.assertIn("<img", html_content)


class TestExport(unittest.TestCase):

    def setUp(self):
        test_record_instance.clean_record()
        self._original = test_record_instance.init_record
        test_record_instance.init_record = True

    def tearDown(self):
        test_record_instance.clean_record()
        test_record_instance.init_record = self._original

    def test_writes_file(self):
        record_action_to_list("ok", None, None)
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "replay.html")
            written = export_replay_studio(target)
            self.assertTrue(os.path.exists(written))
            with open(written, encoding="utf-8") as report:
                content = report.read()
            self.assertIn("<!DOCTYPE html>", content)


if __name__ == "__main__":
    unittest.main()
