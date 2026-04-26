import os
import tempfile
import unittest
from io import BytesIO
from unittest.mock import patch

from PIL import Image

from je_web_runner.utils.executor.action_executor import Executor


def _png_bytes(color=(0, 0, 0), size=(8, 8)) -> bytes:
    image = Image.new("RGB", size, color)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


class TestFailureScreenshot(unittest.TestCase):

    def test_dir_disabled_by_default(self):
        executor = Executor()
        self.assertIsNone(executor.failure_screenshot_dir)
        self.assertIsNone(executor._capture_failure_screenshot(["WR_unknown"]))

    def test_set_dir_creates_directory(self):
        executor = Executor()
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "fails")
            executor.set_failure_screenshot_dir(target)
            self.assertTrue(os.path.isdir(target))
            self.assertEqual(executor.failure_screenshot_dir, target)

    def test_capture_uses_selenium_first(self):
        executor = Executor()
        with tempfile.TemporaryDirectory() as tmpdir, \
                patch("je_web_runner.utils.executor.action_executor._try_selenium_screenshot",
                      return_value=_png_bytes((255, 0, 0))) as selenium_mock, \
                patch("je_web_runner.utils.executor.action_executor._try_playwright_screenshot",
                      return_value=_png_bytes((0, 255, 0))) as pw_mock:
            executor.set_failure_screenshot_dir(tmpdir)
            path = executor._capture_failure_screenshot(["WR_to_url"])
            self.assertIsNotNone(path)
            self.assertTrue(os.path.exists(path))
            selenium_mock.assert_called_once()
            pw_mock.assert_not_called()

    def test_falls_back_to_playwright_when_selenium_missing(self):
        executor = Executor()
        with tempfile.TemporaryDirectory() as tmpdir, \
                patch("je_web_runner.utils.executor.action_executor._try_selenium_screenshot",
                      return_value=None), \
                patch("je_web_runner.utils.executor.action_executor._try_playwright_screenshot",
                      return_value=_png_bytes()):
            executor.set_failure_screenshot_dir(tmpdir)
            path = executor._capture_failure_screenshot(["WR_pw_to_url"])
            self.assertIsNotNone(path)

    def test_capture_returns_none_when_no_backend_active(self):
        executor = Executor()
        with tempfile.TemporaryDirectory() as tmpdir, \
                patch("je_web_runner.utils.executor.action_executor._try_selenium_screenshot",
                      return_value=None), \
                patch("je_web_runner.utils.executor.action_executor._try_playwright_screenshot",
                      return_value=None):
            executor.set_failure_screenshot_dir(tmpdir)
            self.assertIsNone(executor._capture_failure_screenshot(["WR_quit"]))

    def test_execute_action_writes_screenshot_on_failure(self):
        executor = Executor()
        with tempfile.TemporaryDirectory() as tmpdir, \
                patch("je_web_runner.utils.executor.action_executor._try_selenium_screenshot",
                      return_value=_png_bytes()):
            executor.set_failure_screenshot_dir(tmpdir)
            result = executor.execute_action([["WR_definitely_unknown_command"]])
            entries = list(result.values())
            self.assertEqual(len(entries), 1)
            self.assertIn("failure screenshot:", entries[0])
            self.assertGreater(len(os.listdir(tmpdir)), 0)


if __name__ == "__main__":
    unittest.main()
