"""Callbacks, visual regression and the recorder for Playwright (progress #19, fifth batch)."""
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from je_web_runner.utils.callback.callback_function_executor import callback_executor
from je_web_runner.utils.executor.action_executor import executor
from je_web_runner.utils.executor._playwright_commands import PLAYWRIGHT_COMMANDS
from je_web_runner.utils.recorder.browser_recorder import PlaywrightScriptRunner


def _png(color) -> bytes:
    from PIL import Image
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), color).save(buffer, format="PNG")
    return buffer.getvalue()


class TestCallbacks(unittest.TestCase):

    def test_callback_executor_knows_every_playwright_command(self):
        missing = sorted(set(PLAYWRIGHT_COMMANDS) - set(callback_executor.event_dict))
        self.assertEqual(missing, [])


class TestVisualRegression(unittest.TestCase):

    def test_baseline_and_compare_use_the_playwright_screenshot(self):
        from je_web_runner.utils.visual_regression import visual_diff
        wrapper = MagicMock()
        wrapper.screenshot_bytes.side_effect = [_png("white"), _png("white"), _png("black")]
        with tempfile.TemporaryDirectory() as tmp, \
                patch("je_web_runner.webdriver.playwright_wrapper.playwright_wrapper_instance", wrapper):
            baseline = str(Path(tmp) / "home.png")
            visual_diff.playwright_capture_baseline(baseline)
            self.assertTrue(visual_diff.playwright_compare_with_baseline(baseline)["match"])
            result = visual_diff.playwright_compare_with_baseline(baseline, threshold=0)
        self.assertFalse(result["match"])
        self.assertEqual(result["pixel_diff"], 64)


class TestRecorder(unittest.TestCase):

    def test_scripts_run_as_function_bodies_in_the_page(self):
        wrapper = MagicMock()
        wrapper.page.evaluate.return_value = [{"type": "click"}]
        runner = PlaywrightScriptRunner(wrapper)
        self.assertEqual(runner.execute_script("return window.__wr_events;"), [{"type": "click"}])
        wrapper.page.evaluate.assert_called_once_with("() => { return window.__wr_events; }")


class TestCommands(unittest.TestCase):

    def test_commands_are_registered(self):
        for name in ("WR_pw_visual_capture_baseline", "WR_pw_visual_compare", "WR_pw_recorder_start",
                     "WR_pw_recorder_stop", "WR_pw_recorder_pull_events", "WR_pw_recorder_save"):
            self.assertIn(name, executor.event_dict)


if __name__ == "__main__":
    unittest.main()
