"""
感知雜湊(perceptual hash)+ 簡化 SSIM 視覺比對,給 Canvas / WebGL / 圖表
這種「結構一樣但每像素不同」的 UI 用。比 ``visual_regression`` 的 pixel-diff
更耐渲染抖動。

Implements three classic hashes from the imagehash literature without
adding a numpy/imagehash dependency:

* **aHash** (average hash) — fastest, robust to small colour shifts.
* **dHash** (difference hash) — best general balance, sensitive to
  edges/gradients (great for charts).
* **pHash** (perceptual hash with DCT) — most robust to rescaling and
  small visual noise; we implement an 8×8 DCT in pure Python so it stays
  dependency-light.

Plus a tiny grayscale SSIM proxy that doesn't need scipy.

All functions accept ``bytes`` (PNG/JPEG) or ``str``/``Path`` to a file
and return :class:`HashResult` / :class:`SimilarityResult` dataclasses.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, List, Optional, Sequence, Tuple, Union

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class VisualAIError(WebRunnerException):
    """Raised on missing Pillow, bad input, or impossible comparison."""


# ---------- image loading -------------------------------------------------

def _require_pillow():
    try:
        from PIL import Image  # type: ignore[import-not-found]
        return Image
    except ImportError as error:
        raise VisualAIError(
            "Pillow is required for visual_ai. Install: pip install Pillow"
        ) from error


def _load_image(source: Union[bytes, str, Path, Any]) -> Any:
    """Accept bytes / path / PIL.Image and return an open PIL.Image."""
    Image = _require_pillow()
    if hasattr(source, "convert") and hasattr(source, "size"):
        return source  # already a PIL Image
    if isinstance(source, (bytes, bytearray)):
        try:
            return Image.open(BytesIO(bytes(source)))
        except Exception as error:  # noqa: BLE001 — Pillow raises many
            raise VisualAIError(f"cannot decode image bytes: {error!r}") from error
    if isinstance(source, (str, Path)):
        path = Path(source)
        if not path.is_file():
            raise VisualAIError(f"image not found: {path}")
        try:
            return Image.open(path)
        except Exception as error:  # noqa: BLE001
            raise VisualAIError(f"cannot open image {path}: {error!r}") from error
    raise VisualAIError(
        f"unsupported image source: {type(source).__name__}"
    )


# ---------- Region-of-Interest preprocessing ----------------------------

BoundingBox = Tuple[int, int, int, int]  # (left, top, right, bottom)


def _validate_box(box: Any, name: str, *, image_size: Optional[Tuple[int, int]] = None) -> BoundingBox:
    if (not isinstance(box, (tuple, list))) or len(box) != 4:
        raise VisualAIError(f"{name} must be a 4-tuple (left, top, right, bottom)")
    try:
        left, top, right, bottom = (int(v) for v in box)
    except (TypeError, ValueError) as error:
        raise VisualAIError(f"{name} must contain ints: {error!r}") from error
    if right <= left or bottom <= top:
        raise VisualAIError(
            f"{name} must satisfy right>left and bottom>top, got {box}"
        )
    if left < 0 or top < 0:
        raise VisualAIError(f"{name} cannot have negative origin: {box}")
    if image_size is not None:
        w, h = image_size
        if right > w or bottom > h:
            raise VisualAIError(
                f"{name} {box} exceeds image size {image_size}"
            )
    return (left, top, right, bottom)


def _preprocess(
    img: Any,
    *,
    crop_box: Optional[BoundingBox] = None,
    mask_boxes: Optional[Sequence[BoundingBox]] = None,
    mask_fill: int = 0,
) -> Any:
    """
    對單張圖套上 crop_box(只留該區)以及 mask_boxes(填灰階黑遮罩)。
    Mutates a copy — original PIL image is untouched.
    """
    _require_pillow()  # ensure Pillow is importable
    working = img.copy()
    if mask_boxes:
        from PIL import ImageDraw  # type: ignore[import-not-found]
        draw = ImageDraw.Draw(working)
        for box in mask_boxes:
            checked = _validate_box(box, "mask_box", image_size=working.size)
            fill = (mask_fill, mask_fill, mask_fill) if working.mode == "RGB" else mask_fill
            draw.rectangle(checked, fill=fill)
    if crop_box is not None:
        checked = _validate_box(crop_box, "crop_box", image_size=working.size)
        working = working.crop(checked)
    return working


def _load_and_preprocess(
    source: Union[bytes, str, Path, Any],
    *,
    crop_box: Optional[BoundingBox] = None,
    mask_boxes: Optional[Sequence[BoundingBox]] = None,
) -> Any:
    img = _load_image(source)
    if crop_box is None and not mask_boxes:
        return img
    return _preprocess(img, crop_box=crop_box, mask_boxes=mask_boxes)


def _to_grayscale_pixels(img: Any, size: int) -> List[int]:
    Image = _require_pillow()
    resized = img.convert("L").resize((size, size), Image.Resampling.LANCZOS)
    return list(resized.getdata())


# ---------- hashes --------------------------------------------------------

@dataclass(frozen=True)
class HashResult:
    """A single perceptual hash with its kind and bit string."""

    kind: str
    bits: str  # "0101…" of length kind-dependent

    def hex(self) -> str:
        # pad bits to multiple of 4
        bits = self.bits
        if len(bits) % 4:
            bits = bits + "0" * (4 - len(bits) % 4)
        return f"{int(bits, 2):x}".zfill(len(bits) // 4)


def _bits_to_str(values: List[int], threshold: float) -> str:
    return "".join("1" if v >= threshold else "0" for v in values)


def average_hash(
    source: Union[bytes, str, Path, Any],
    *,
    size: int = 8,
    crop_box: Optional[BoundingBox] = None,
    mask_boxes: Optional[Sequence[BoundingBox]] = None,
) -> HashResult:
    """
    aHash:縮成 size×size 灰階,以平均值二值化。
    Fast and surprisingly accurate for screenshot-scale comparisons.
    ``crop_box`` / ``mask_boxes`` apply before resizing so the hash
    reflects only the region you care about.
    """
    img = _load_and_preprocess(source, crop_box=crop_box, mask_boxes=mask_boxes)
    pixels = _to_grayscale_pixels(img, size)
    if not pixels:
        raise VisualAIError("empty image after resize")
    mean = sum(pixels) / len(pixels)
    return HashResult(kind="aHash", bits=_bits_to_str(pixels, mean))


def difference_hash(
    source: Union[bytes, str, Path, Any],
    *,
    size: int = 8,
    crop_box: Optional[BoundingBox] = None,
    mask_boxes: Optional[Sequence[BoundingBox]] = None,
) -> HashResult:
    """
    dHash:每列相鄰像素的差值二值化(size+1 寬)。
    Strong on gradients and edges — pairs well with charts.
    """
    img = _load_and_preprocess(source, crop_box=crop_box, mask_boxes=mask_boxes)
    pixels = _to_grayscale_pixels(img, size + 1)  # need one extra column
    bits: List[int] = []
    width = size + 1
    for row in range(size + 1):
        # only compare within row; only use rows 0..size-1
        if row >= size:
            continue
        row_start = row * width
        for col in range(size):
            left = pixels[row_start + col]
            right = pixels[row_start + col + 1]
            bits.append(1 if left < right else 0)
    return HashResult(kind="dHash", bits="".join(str(b) for b in bits))


# ---------- pHash (8×8 DCT) ----------------------------------------------

def _dct_1d(vector: List[float]) -> List[float]:
    """Standard DCT-II implementation. O(n^2) but n is tiny (32) here."""
    n = len(vector)
    out = [0.0] * n
    for k in range(n):
        s = 0.0
        for i in range(n):
            s += vector[i] * math.cos(math.pi * (2 * i + 1) * k / (2 * n))
        out[k] = s
    return out


def perceptual_hash(
    source: Union[bytes, str, Path, Any],
    *,
    size: int = 32,
    hash_size: int = 8,
    crop_box: Optional[BoundingBox] = None,
    mask_boxes: Optional[Sequence[BoundingBox]] = None,
) -> HashResult:
    """
    pHash:對 32×32 灰階做 2D DCT,取左上 8×8 低頻區與其中位數二值化。
    Most robust of the three to scaling and JPEG-style noise.
    """
    img = _load_and_preprocess(source, crop_box=crop_box, mask_boxes=mask_boxes)
    pixels = _to_grayscale_pixels(img, size)
    matrix: List[List[float]] = [
        [float(pixels[row * size + col]) for col in range(size)]
        for row in range(size)
    ]
    # rows
    matrix = [_dct_1d(row) for row in matrix]
    # cols
    cols_transposed: List[List[float]] = [
        [matrix[r][c] for r in range(size)] for c in range(size)
    ]
    cols_transposed = [_dct_1d(col) for col in cols_transposed]
    # take low-freq top-left hash_size×hash_size, skip DC (0,0)
    low_freq: List[float] = []
    for c in range(hash_size):
        for r in range(hash_size):
            if r == 0 and c == 0:
                continue
            low_freq.append(cols_transposed[c][r])
    if not low_freq:
        raise VisualAIError("hash_size too small to compute pHash")
    sorted_vals = sorted(low_freq)
    mid = sorted_vals[len(sorted_vals) // 2]
    bits = "".join("1" if v >= mid else "0" for v in low_freq)
    return HashResult(kind="pHash", bits=bits)


# ---------- distance / similarity -----------------------------------------

def hamming_distance(a: HashResult, b: HashResult) -> int:
    """Bit count of XOR. Hashes must be the same kind and length."""
    if a.kind != b.kind:
        raise VisualAIError(f"hash kinds differ: {a.kind} vs {b.kind}")
    if len(a.bits) != len(b.bits):
        raise VisualAIError(
            f"hash lengths differ: {len(a.bits)} vs {len(b.bits)}"
        )
    return sum(1 for x, y in zip(a.bits, b.bits) if x != y)


def hash_similarity(a: HashResult, b: HashResult) -> float:
    """``1 - hamming/bits`` — 1.0 means identical, 0.0 means inverted."""
    dist = hamming_distance(a, b)
    total = len(a.bits)
    return 1.0 - (dist / total) if total else 0.0


@dataclass
class SimilarityResult:
    """Outcome of :func:`compare_images`."""

    ahash_similarity: float
    dhash_similarity: float
    phash_similarity: float
    ssim_proxy: float
    composite: float
    passed: bool
    threshold: float


def _ssim_proxy(
    source_a: Union[bytes, str, Path, Any],
    source_b: Union[bytes, str, Path, Any],
    *,
    size: int = 32,
    crop_box: Optional[BoundingBox] = None,
    mask_boxes: Optional[Sequence[BoundingBox]] = None,
) -> float:
    """
    一個輕量級 SSIM 取代:用 mean / var / covariance 的灰階近似。
    Returns a number in [-1, 1] (typically 0..1 for real images). It's
    NOT a real SSIM but is monotonic for the use cases we care about
    (charts that subtly drift vs ones that don't).
    """
    Image = _require_pillow()
    img_a = _load_and_preprocess(source_a, crop_box=crop_box, mask_boxes=mask_boxes)
    img_b = _load_and_preprocess(source_b, crop_box=crop_box, mask_boxes=mask_boxes)
    a = img_a.convert("L").resize((size, size), Image.Resampling.LANCZOS)
    b = img_b.convert("L").resize((size, size), Image.Resampling.LANCZOS)
    pa = [p / 255.0 for p in a.getdata()]
    pb = [p / 255.0 for p in b.getdata()]
    n = len(pa)
    if n == 0:
        return 0.0
    mean_a = sum(pa) / n
    mean_b = sum(pb) / n
    var_a = sum((x - mean_a) ** 2 for x in pa) / n
    var_b = sum((y - mean_b) ** 2 for y in pb) / n
    cov = sum((x - mean_a) * (y - mean_b) for x, y in zip(pa, pb)) / n
    c1 = 0.01 ** 2
    c2 = 0.03 ** 2
    num = (2 * mean_a * mean_b + c1) * (2 * cov + c2)
    den = (mean_a ** 2 + mean_b ** 2 + c1) * (var_a + var_b + c2)
    if den == 0:
        return 1.0 if num == 0 else 0.0
    return max(-1.0, min(1.0, num / den))


def compare_images(
    source_a: Union[bytes, str, Path, Any],
    source_b: Union[bytes, str, Path, Any],
    *,
    threshold: float = 0.9,
    weights: Tuple[float, float, float, float] = (0.2, 0.3, 0.3, 0.2),
    crop_box: Optional[BoundingBox] = None,
    mask_boxes: Optional[Sequence[BoundingBox]] = None,
) -> SimilarityResult:
    """
    跑三種 hash + SSIM proxy,加權算出 composite 相似度,跟 threshold 比。
    Returns a :class:`SimilarityResult`; ``passed`` is True when the
    composite score is at or above ``threshold``.

    ``weights`` is ``(aHash, dHash, pHash, ssim)`` — adjust to favour
    structural similarity (raise pHash/ssim) or pixel-level (raise aHash).

    ``crop_box`` (left, top, right, bottom) restricts the comparison to a
    region; ``mask_boxes`` blacks out dynamic regions (clocks, A/B
    banners) before the hash is computed. Both apply to *both* images
    identically — bounding boxes are absolute pixel coords from the
    top-left of each input image.
    """
    if abs(sum(weights) - 1.0) > 0.001:
        raise VisualAIError(f"weights must sum to 1.0, got {sum(weights)}")
    if threshold < 0 or threshold > 1:
        raise VisualAIError(f"threshold must be in [0,1], got {threshold}")

    hash_kwargs = {"crop_box": crop_box, "mask_boxes": mask_boxes}
    a_a = average_hash(source_a, **hash_kwargs)
    a_b = average_hash(source_b, **hash_kwargs)
    d_a = difference_hash(source_a, **hash_kwargs)
    d_b = difference_hash(source_b, **hash_kwargs)
    p_a = perceptual_hash(source_a, **hash_kwargs)
    p_b = perceptual_hash(source_b, **hash_kwargs)

    a_sim = hash_similarity(a_a, a_b)
    d_sim = hash_similarity(d_a, d_b)
    p_sim = hash_similarity(p_a, p_b)
    s_sim = max(0.0, _ssim_proxy(source_a, source_b, **hash_kwargs))

    composite = (
        weights[0] * a_sim
        + weights[1] * d_sim
        + weights[2] * p_sim
        + weights[3] * s_sim
    )
    result = SimilarityResult(
        ahash_similarity=round(a_sim, 4),
        dhash_similarity=round(d_sim, 4),
        phash_similarity=round(p_sim, 4),
        ssim_proxy=round(s_sim, 4),
        composite=round(composite, 4),
        passed=composite >= threshold,
        threshold=threshold,
    )
    web_runner_logger.info(
        f"compare_images: composite={result.composite:.3f} "
        f"threshold={threshold} passed={result.passed}"
    )
    return result


def assert_visual_similar(
    baseline: Union[bytes, str, Path, Any],
    candidate: Union[bytes, str, Path, Any],
    *,
    threshold: float = 0.9,
    weights: Tuple[float, float, float, float] = (0.2, 0.3, 0.3, 0.2),
    crop_box: Optional[BoundingBox] = None,
    mask_boxes: Optional[Sequence[BoundingBox]] = None,
) -> SimilarityResult:
    """
    Raises :class:`VisualAIError` 當 composite 相似度低於 threshold。
    Supports the same ``crop_box`` / ``mask_boxes`` parameters as
    :func:`compare_images`.
    """
    result = compare_images(
        baseline, candidate,
        threshold=threshold, weights=weights,
        crop_box=crop_box, mask_boxes=mask_boxes,
    )
    if not result.passed:
        raise VisualAIError(
            f"visual similarity {result.composite:.3f} below threshold {threshold} "
            f"(aHash={result.ahash_similarity}, dHash={result.dhash_similarity}, "
            f"pHash={result.phash_similarity}, ssim={result.ssim_proxy})"
        )
    return result
