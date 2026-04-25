import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from je_web_runner.utils.lighthouse.lighthouse_runner import (
    LighthouseError,
    assert_scores,
    run_lighthouse,
)


def _fake_report():
    return {
        "categories": {
            "performance": {"score": 0.9},
            "accessibility": {"score": 0.95},
            "best-practices": {"score": 0.8},
            "seo": {"score": 1.0},
            "pwa": {"score": 0.0},
        }
    }


class TestRunLighthouse(unittest.TestCase):

    def test_invalid_url_raises(self):
        with self.assertRaises(LighthouseError):
            run_lighthouse("ftp://example.com")

    def test_runs_and_summarises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = os.path.join(tmpdir, "lh.json")
            Path(report_path).write_text(json.dumps(_fake_report()), encoding="utf-8")
            completed = subprocess.CompletedProcess([], 0, stdout="", stderr="")
            with patch(
                "je_web_runner.utils.lighthouse.lighthouse_runner.subprocess.run",
                return_value=completed,
            ) as run_mock:
                result = run_lighthouse(
                    "https://example.com", output_path=report_path,
                )
                self.assertEqual(result["scores"]["performance"], 0.9)
                self.assertEqual(result["scores"]["accessibility"], 0.95)
                self.assertEqual(result["report_path"], report_path)
                cmd = run_mock.call_args.args[0]
                self.assertEqual(cmd[0], "lighthouse")
                self.assertIn("https://example.com", cmd)

    def test_non_zero_exit_raises(self):
        completed = subprocess.CompletedProcess([], 1, stdout="", stderr="boom")
        with patch(
            "je_web_runner.utils.lighthouse.lighthouse_runner.subprocess.run",
            return_value=completed,
        ):
            with self.assertRaises(LighthouseError):
                run_lighthouse("https://example.com")

    def test_missing_executable_raises(self):
        with patch(
            "je_web_runner.utils.lighthouse.lighthouse_runner.subprocess.run",
            side_effect=FileNotFoundError(),
        ):
            with self.assertRaises(LighthouseError):
                run_lighthouse("https://example.com")

    def test_timeout_raises(self):
        with patch(
            "je_web_runner.utils.lighthouse.lighthouse_runner.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="lighthouse", timeout=1),
        ):
            with self.assertRaises(LighthouseError):
                run_lighthouse("https://example.com")

    def test_chrome_flags_appended(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = os.path.join(tmpdir, "lh.json")
            Path(report_path).write_text(json.dumps(_fake_report()), encoding="utf-8")
            completed = subprocess.CompletedProcess([], 0, stdout="", stderr="")
            with patch(
                "je_web_runner.utils.lighthouse.lighthouse_runner.subprocess.run",
                return_value=completed,
            ) as run_mock:
                run_lighthouse(
                    "https://example.com",
                    output_path=report_path,
                    chrome_flags=["--headless=new", "--no-sandbox"],
                )
                cmd = run_mock.call_args.args[0]
                self.assertTrue(any(arg.startswith("--chrome-flags=") for arg in cmd))


class TestAssertScores(unittest.TestCase):

    def test_pass_when_above_threshold(self):
        result = {"scores": {"performance": 0.9, "accessibility": 0.95}}
        assert_scores(result, {"performance": 0.8, "accessibility": 0.9})

    def test_fail_when_below_threshold(self):
        result = {"scores": {"performance": 0.5}}
        with self.assertRaises(LighthouseError):
            assert_scores(result, {"performance": 0.8})

    def test_missing_score_treated_as_breach(self):
        result = {"scores": {}}
        with self.assertRaises(LighthouseError):
            assert_scores(result, {"performance": 0.8})

    def test_missing_scores_dict_raises(self):
        with self.assertRaises(LighthouseError):
            assert_scores({}, {"performance": 0.8})


if __name__ == "__main__":
    unittest.main()
