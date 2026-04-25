import os
import tempfile
import unittest
from io import BytesIO
from unittest.mock import patch

from PIL import Image

from je_web_runner.utils.visual_regression.visual_diff import (
    VisualRegressionError,
    capture_baseline,
    compare_with_baseline,
)


def _png_bytes(color: tuple, size: tuple = (40, 40)) -> bytes:
    image = Image.new("RGB", size, color)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


class TestVisualDiff(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.baseline = os.path.join(self.tmpdir.name, "baseline.png")

    def tearDown(self):
        self.tmpdir.cleanup()

    @patch("je_web_runner.utils.visual_regression.visual_diff.webdriver_wrapper_instance")
    def test_capture_baseline_writes_png(self, wrapper):
        wrapper.get_screenshot_as_png.return_value = _png_bytes((255, 0, 0))
        path = capture_baseline(self.baseline)
        self.assertTrue(os.path.exists(path))
        self.assertEqual(path, self.baseline)

    @patch("je_web_runner.utils.visual_regression.visual_diff.webdriver_wrapper_instance")
    def test_compare_match_when_identical(self, wrapper):
        red = _png_bytes((255, 0, 0))
        wrapper.get_screenshot_as_png.return_value = red
        capture_baseline(self.baseline)
        wrapper.get_screenshot_as_png.return_value = red  # same content
        result = compare_with_baseline(self.baseline)
        self.assertTrue(result["match"])
        self.assertEqual(result["pixel_diff"], 0)
        self.assertIsNone(result["diff_image_path"])

    @patch("je_web_runner.utils.visual_regression.visual_diff.webdriver_wrapper_instance")
    def test_compare_detects_difference_and_writes_diff(self, wrapper):
        wrapper.get_screenshot_as_png.return_value = _png_bytes((255, 0, 0))
        capture_baseline(self.baseline)
        wrapper.get_screenshot_as_png.return_value = _png_bytes((0, 255, 0))
        result = compare_with_baseline(self.baseline)
        self.assertFalse(result["match"])
        self.assertGreater(result["pixel_diff"], 0)
        self.assertTrue(os.path.exists(result["diff_image_path"]))

    @patch("je_web_runner.utils.visual_regression.visual_diff.webdriver_wrapper_instance")
    def test_compare_detects_size_mismatch(self, wrapper):
        wrapper.get_screenshot_as_png.return_value = _png_bytes((255, 0, 0), size=(40, 40))
        capture_baseline(self.baseline)
        wrapper.get_screenshot_as_png.return_value = _png_bytes((255, 0, 0), size=(50, 50))
        result = compare_with_baseline(self.baseline)
        self.assertFalse(result["match"])
        self.assertEqual(result["reason"], "size mismatch")

    def test_missing_baseline_raises(self):
        with patch("je_web_runner.utils.visual_regression.visual_diff.webdriver_wrapper_instance") as wrapper:
            wrapper.get_screenshot_as_png.return_value = _png_bytes((0, 0, 0))
            with self.assertRaises(VisualRegressionError):
                compare_with_baseline(os.path.join(self.tmpdir.name, "missing.png"))

    @patch("je_web_runner.utils.visual_regression.visual_diff.webdriver_wrapper_instance")
    def test_threshold_allows_small_difference(self, wrapper):
        wrapper.get_screenshot_as_png.return_value = _png_bytes((255, 0, 0))
        capture_baseline(self.baseline)
        wrapper.get_screenshot_as_png.return_value = _png_bytes((0, 255, 0))
        result = compare_with_baseline(self.baseline, threshold=10_000)
        self.assertTrue(result["match"])
        self.assertGreater(result["pixel_diff"], 0)


if __name__ == "__main__":
    unittest.main()
