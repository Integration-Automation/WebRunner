"""
視覺回歸比對工具：擷取目前頁面截圖並與基準圖比較差異。
Visual regression utility: capture page screenshots and diff them against a baseline.

Pillow 是軟相依：使用此功能時才匯入，未安裝時會丟出明確錯誤。
Pillow is a soft dependency: imported lazily so the rest of WebRunner runs
without it; clear error is raised if the user invokes a visual command without
Pillow installed.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.webdriver.webdriver_wrapper import webdriver_wrapper_instance


class VisualRegressionError(WebRunnerException):
    """Raised when a visual regression operation cannot complete."""


def _require_pillow():
    """Import Pillow lazily; surface a clear install hint when missing."""
    try:
        from PIL import Image, ImageChops  # type: ignore[import-not-found]
        return Image, ImageChops
    except ImportError as error:
        raise VisualRegressionError(
            "Pillow is required for visual regression. Install with: pip install Pillow"
        ) from error


def _capture_png_bytes() -> bytes:
    """Pull a PNG screenshot from the current driver via the WebRunner wrapper."""
    png = webdriver_wrapper_instance.get_screenshot_as_png()
    if not png:
        raise VisualRegressionError("driver returned no screenshot bytes")
    return png


def _ensure_parent(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def capture_baseline(baseline_path: str) -> str:
    """
    擷取當前頁面並儲存為基準圖
    Capture the current page and save it as the baseline image.

    :param baseline_path: 基準圖輸出路徑 / output path for the baseline PNG
    :return: 基準圖路徑 / the baseline path written
    """
    web_runner_logger.info(f"capture_baseline: {baseline_path}")
    _ensure_parent(baseline_path)
    png = _capture_png_bytes()
    with open(baseline_path, "wb") as out_file:
        out_file.write(png)
    return baseline_path


def _count_diff_pixels(diff_image) -> int:
    """Return number of pixels with any non-zero channel in the diff image."""
    # Use raw bytes (RGB → 3 bytes/pixel) to stay compatible after Pillow 14
    # removes Image.getdata().
    flat = diff_image.tobytes()
    return sum(1 for i in range(0, len(flat), 3) if flat[i] or flat[i + 1] or flat[i + 2])


def compare_with_baseline(
    baseline_path: str,
    diff_path: Optional[str] = None,
    current_path: Optional[str] = None,
    threshold: int = 0,
) -> dict:
    """
    擷取目前頁面並與基準圖比較
    Capture the current page and compare it against a baseline.

    :param baseline_path: 基準圖路徑 / path to the baseline PNG
    :param diff_path: 若有差異，輸出差異圖到此路徑 (預設沿用 baseline 名稱)
                       Output path for the diff image when differences exist.
    :param current_path: 同時保存目前截圖到此路徑 (預設不保存)
                          Optional path to also persist the current screenshot.
    :param threshold: 容忍像素差異數量 / pixel-difference tolerance
    :return: dict 包含 match / pixel_diff / diff_image_path / 大小資訊
              dict with match / pixel_diff / diff_image_path / size info
    """
    web_runner_logger.info(f"compare_with_baseline: {baseline_path}")
    if not Path(baseline_path).exists():
        raise VisualRegressionError(f"baseline not found: {baseline_path}")
    pil_image, pil_image_chops = _require_pillow()

    current_png = _capture_png_bytes()
    if current_path:
        _ensure_parent(current_path)
        with open(current_path, "wb") as out_file:
            out_file.write(current_png)

    baseline_image = pil_image.open(baseline_path).convert("RGB")
    current_image = pil_image.open(BytesIO(current_png)).convert("RGB")

    if baseline_image.size != current_image.size:
        return {
            "match": False,
            "pixel_diff": -1,
            "diff_image_path": None,
            "baseline_size": baseline_image.size,
            "current_size": current_image.size,
            "reason": "size mismatch",
        }

    diff_image = pil_image_chops.difference(baseline_image, current_image)
    if diff_image.getbbox() is None:
        return {"match": True, "pixel_diff": 0, "diff_image_path": None}

    pixel_diff = _count_diff_pixels(diff_image)
    target = diff_path or baseline_path.replace(".png", "_diff.png")
    _ensure_parent(target)
    diff_image.save(target)
    return {
        "match": pixel_diff <= threshold,
        "pixel_diff": pixel_diff,
        "diff_image_path": target,
    }
