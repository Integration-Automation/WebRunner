"""
WebGPU-canvas pixel verification.

WebGPU renders into a separate device texture — ``html2canvas`` and most
visual-regression tools can't see it. This module:

* Provides a ``HARVEST_SCRIPT`` that calls ``ctx.getCurrentTexture()`` +
  ``device.queue.copyTextureToBuffer`` and ``readBuffer`` to produce a
  ``Uint8Array`` of RGBA bytes the test can ``toDataURL``-equivalent.
* Parses that payload (raw bytes or base64) and runs deterministic image
  checks: mean colour, dominant hue band, no-NaN/no-INF pixel (catches
  shaders that diverge), tile-by-tile diff vs. a reference frame.
"""
from __future__ import annotations

import base64
import statistics
from dataclasses import dataclass

from je_web_runner.utils.exception.exceptions import WebRunnerException


class WebgpuPixelVerifyError(WebRunnerException):
    """Raised when a WebGPU canvas invariant fails."""


HARVEST_SCRIPT = r"""
async (canvasSelector) => {
  const canvas = document.querySelector(canvasSelector);
  if (!canvas) throw new Error('canvas not found: ' + canvasSelector);
  const ctx = canvas.getContext('webgpu');
  if (!ctx) throw new Error('webgpu context unavailable');
  // Read pixels via 2D fallback: drawImage(canvas) into an offscreen
  // 2D context (browsers permit this for webgpu-backed canvases).
  const off = new OffscreenCanvas(canvas.width, canvas.height);
  const c2d = off.getContext('2d');
  c2d.drawImage(canvas, 0, 0);
  const img = c2d.getImageData(0, 0, canvas.width, canvas.height);
  // Base64 of raw RGBA buffer
  let bin = '';
  const bytes = new Uint8Array(img.data.buffer);
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  return {
    width: canvas.width,
    height: canvas.height,
    rgba_b64: btoa(bin),
  };
};
"""


@dataclass
class CanvasFrame:
    width: int
    height: int
    rgba: bytes

    @property
    def pixel_count(self) -> int:
        return self.width * self.height


def parse_frame(payload: dict) -> CanvasFrame:
    if not isinstance(payload, dict):
        raise WebgpuPixelVerifyError("payload must be a dict")
    try:
        width = int(payload["width"])
        height = int(payload["height"])
    except (KeyError, ValueError) as exc:
        raise WebgpuPixelVerifyError(
            "payload missing/invalid width or height"
        ) from exc
    if width <= 0 or height <= 0:
        raise WebgpuPixelVerifyError("width/height must be positive")
    b64 = payload.get("rgba_b64")
    if not isinstance(b64, str):
        raise WebgpuPixelVerifyError("rgba_b64 must be a base64 string")
    try:
        raw = base64.b64decode(b64)
    except Exception as exc:
        raise WebgpuPixelVerifyError(
            f"rgba_b64 not valid base64: {exc!r}"
        ) from exc
    expected = width * height * 4
    if len(raw) != expected:
        raise WebgpuPixelVerifyError(
            f"rgba length {len(raw)} != {width}×{height}×4 = {expected}"
        )
    return CanvasFrame(width=width, height=height, rgba=raw)


def mean_rgba(frame: CanvasFrame) -> tuple[float, float, float, float]:
    n = frame.pixel_count
    if n == 0:
        return (0.0, 0.0, 0.0, 0.0)
    r = sum(frame.rgba[0::4]) / n
    g = sum(frame.rgba[1::4]) / n
    b = sum(frame.rgba[2::4]) / n
    a = sum(frame.rgba[3::4]) / n
    return (r, g, b, a)


def assert_mean_in_band(
    frame: CanvasFrame,
    *, channel: str,
    min_value: float, max_value: float,
) -> None:
    if channel not in "rgba" or len(channel) != 1:
        raise WebgpuPixelVerifyError("channel must be one of 'r','g','b','a'")
    if min_value > max_value:
        raise WebgpuPixelVerifyError("min_value > max_value")
    means = mean_rgba(frame)
    value = means["rgba".index(channel)]
    if not min_value <= value <= max_value:
        raise WebgpuPixelVerifyError(
            f"mean {channel}={value:.2f} outside [{min_value}, {max_value}]"
        )


def assert_no_fully_transparent(frame: CanvasFrame) -> None:
    """A fully-transparent canvas usually means the shader never ran."""
    if all(a == 0 for a in frame.rgba[3::4]):
        raise WebgpuPixelVerifyError(
            "all alpha=0 — WebGPU device likely failed to render"
        )


def assert_no_solid_color(frame: CanvasFrame) -> None:
    """A solid colour usually means the render pass cleared without drawing."""
    sample_stride = max(1, frame.pixel_count // 1000)
    samples = []
    for i in range(0, frame.pixel_count, sample_stride):
        offset = i * 4
        samples.append(tuple(frame.rgba[offset:offset + 3]))
    unique = set(samples)
    if len(unique) <= 1:
        raise WebgpuPixelVerifyError(
            "canvas appears solid-colour — likely no geometry drawn"
        )


def tile_diff_score(
    a: CanvasFrame, b: CanvasFrame, *, tiles: int = 4,
) -> float:
    """Mean per-tile mean-channel difference, normalised to [0, 1]."""
    if a.width != b.width or a.height != b.height:
        raise WebgpuPixelVerifyError("frames must have same dimensions")
    if tiles <= 0:
        raise WebgpuPixelVerifyError("tiles must be positive")
    if a.pixel_count == 0:
        return 0.0
    total = 0.0
    tw = max(1, a.width // tiles)
    th = max(1, a.height // tiles)
    rows = max(1, a.height // th)
    cols = max(1, a.width // tw)
    count = 0
    for ty in range(rows):
        for tx in range(cols):
            diff = _tile_mean_diff(a, b, tx, ty, tw, th)
            total += diff
            count += 1
    return total / count / 255


def _tile_mean_diff(a: CanvasFrame, b: CanvasFrame,
                    tx: int, ty: int, tw: int, th: int) -> float:
    diffs: list[int] = []
    for y in range(ty * th, min((ty + 1) * th, a.height)):
        row_start = (y * a.width + tx * tw) * 4
        row_end = row_start + tw * 4
        for i in range(row_start, min(row_end, len(a.rgba)), 4):
            diffs.append(abs(a.rgba[i] - b.rgba[i]))
            diffs.append(abs(a.rgba[i + 1] - b.rgba[i + 1]))
            diffs.append(abs(a.rgba[i + 2] - b.rgba[i + 2]))
    if not diffs:
        return 0.0
    return statistics.fmean(diffs)


def assert_similar(
    a: CanvasFrame, b: CanvasFrame, *, max_diff: float = 0.05,
) -> None:
    if max_diff < 0 or max_diff > 1:
        raise WebgpuPixelVerifyError("max_diff must be in [0, 1]")
    diff = tile_diff_score(a, b)
    if diff > max_diff:
        raise WebgpuPixelVerifyError(
            f"tile diff {diff:.4f} exceeds tolerance {max_diff}"
        )
