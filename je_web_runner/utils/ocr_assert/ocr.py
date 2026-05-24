"""
Canvas / WebGL / 圖片內文字 OCR 斷言。補 ``visual_ai`` 只做感知雜湊的缺口
─ 當你想斷言「圖表標籤是 'Q4 2025'」而不是「兩張圖看起來一樣」時用這個。

Thin wrapper around `pytesseract` + Pillow that normalises whitespace,
strips diacritics, and offers a couple of comparison modes (exact,
contains, fuzzy ratio). Tesseract is the only realistic pure-Python
option that runs offline; cloud OCR adapters can be added later via
the same :class:`OcrBackend` protocol.
"""
from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, List, Optional, Sequence, Union

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class OcrAssertError(WebRunnerException):
    """Raised on missing OCR backend, unreadable image, or failed assertion."""


_WHITESPACE_RE = re.compile(r"\s+")


# ---------- normalisation ------------------------------------------------

def normalise_text(text: str, *, lowercase: bool = True, strip_accents: bool = True) -> str:
    """Collapse whitespace, optionally lowercase + strip combining marks."""
    if not isinstance(text, str):
        raise OcrAssertError(f"normalise_text expected str, got {type(text).__name__}")
    out = text
    if strip_accents:
        out = "".join(
            ch for ch in unicodedata.normalize("NFKD", out)
            if not unicodedata.combining(ch)
        )
    if lowercase:
        out = out.lower()
    out = _WHITESPACE_RE.sub(" ", out).strip()
    return out


def fuzzy_ratio(a: str, b: str) -> float:
    """0..1 similarity ratio after :func:`normalise_text`."""
    return difflib.SequenceMatcher(None, normalise_text(a), normalise_text(b)).ratio()


# ---------- OCR backend --------------------------------------------------

OcrBackend = Callable[[Any], str]


def _require_pytesseract() -> Any:
    try:
        import pytesseract  # type: ignore[import-not-found]
        return pytesseract
    except ImportError as error:
        raise OcrAssertError(
            "pytesseract is required for ocr_assert. "
            "Install: pip install pytesseract Pillow (and the tesseract binary)."
        ) from error


def _require_pil() -> Any:
    try:
        from PIL import Image  # type: ignore[import-not-found]
        return Image
    except ImportError as error:
        raise OcrAssertError(
            "Pillow is required for ocr_assert. Install: pip install Pillow"
        ) from error


def _open_image(source: Union[bytes, str, Path, Any]) -> Any:
    image_cls = _require_pil()
    if isinstance(source, (bytes, bytearray)):
        from io import BytesIO
        return image_cls.open(BytesIO(source))
    if isinstance(source, (str, Path)):
        path = Path(source)
        if not path.exists():
            raise OcrAssertError(f"image not found: {path}")
        return image_cls.open(path)
    if hasattr(source, "convert"):
        return source
    raise OcrAssertError(
        f"ocr source must be bytes/path/PIL.Image, got {type(source).__name__}"
    )


def tesseract_backend(
    *,
    lang: str = "eng",
    config: str = "--psm 6",
) -> OcrBackend:
    """Return a callable that extracts text from an image using Tesseract."""
    pytesseract = _require_pytesseract()

    def _extract(source: Any) -> str:
        image = _open_image(source)
        try:
            return pytesseract.image_to_string(image, lang=lang, config=config)
        except Exception as error:  # pytesseract raises a custom error class
            raise OcrAssertError(f"tesseract failed: {error!r}") from error

    return _extract


def extract_text(
    source: Union[bytes, str, Path, Any],
    *,
    backend: Optional[OcrBackend] = None,
) -> str:
    """Run OCR on a screenshot / image and return the raw recognised text."""
    runner = backend or tesseract_backend()
    text = runner(source)
    if not isinstance(text, str):
        raise OcrAssertError(
            f"OCR backend returned {type(text).__name__}, expected str"
        )
    return text


# ---------- assertions --------------------------------------------------

@dataclass
class OcrMatchResult:
    """Outcome of an OCR assertion."""

    matched: bool
    mode: str
    needle: str
    haystack: str
    score: float = 0.0
    notes: List[str] = field(default_factory=list)

    def raise_if_failed(self) -> None:
        if not self.matched:
            preview = self.haystack[:200].replace("\n", "\\n")
            raise OcrAssertError(
                f"OCR assertion failed (mode={self.mode}, score={self.score:.2f}). "
                f"needle={self.needle!r} haystack[:200]={preview!r}"
            )


def assert_text_contains(
    source: Union[bytes, str, Path, Any],
    needle: str,
    *,
    backend: Optional[OcrBackend] = None,
    case_sensitive: bool = False,
) -> OcrMatchResult:
    """Assert that ``needle`` appears in the OCR output (whitespace-collapsed)."""
    if not isinstance(needle, str) or not needle:
        raise OcrAssertError("needle must be a non-empty string")
    raw = extract_text(source, backend=backend)
    if case_sensitive:
        haystack_n = _WHITESPACE_RE.sub(" ", raw).strip()
        needle_n = _WHITESPACE_RE.sub(" ", needle).strip()
    else:
        haystack_n = normalise_text(raw)
        needle_n = normalise_text(needle)
    matched = needle_n in haystack_n
    result = OcrMatchResult(
        matched=matched,
        mode="contains",
        needle=needle_n,
        haystack=haystack_n,
        score=1.0 if matched else 0.0,
    )
    if not matched:
        web_runner_logger.warning(
            f"ocr_assert.contains miss: needle={needle_n!r}"
        )
    return result


def assert_text_fuzzy(
    source: Union[bytes, str, Path, Any],
    expected: str,
    *,
    min_ratio: float = 0.8,
    backend: Optional[OcrBackend] = None,
) -> OcrMatchResult:
    """Assert that the OCR output is ``min_ratio``-similar to ``expected``."""
    if not 0.0 < min_ratio <= 1.0:
        raise OcrAssertError("min_ratio must be in (0, 1]")
    raw = extract_text(source, backend=backend)
    haystack_n = normalise_text(raw)
    expected_n = normalise_text(expected)
    score = difflib.SequenceMatcher(None, expected_n, haystack_n).ratio()
    matched = score >= min_ratio
    return OcrMatchResult(
        matched=matched,
        mode="fuzzy",
        needle=expected_n,
        haystack=haystack_n,
        score=round(score, 4),
        notes=[f"min_ratio={min_ratio}"],
    )


def assert_text_any(
    source: Union[bytes, str, Path, Any],
    candidates: Sequence[str],
    *,
    backend: Optional[OcrBackend] = None,
) -> OcrMatchResult:
    """Assert that at least one ``candidate`` appears in the OCR output."""
    if not candidates:
        raise OcrAssertError("candidates must be a non-empty sequence")
    raw = extract_text(source, backend=backend)
    haystack_n = normalise_text(raw)
    for needle in candidates:
        if normalise_text(needle) in haystack_n:
            return OcrMatchResult(
                matched=True,
                mode="any",
                needle=needle,
                haystack=haystack_n,
                score=1.0,
                notes=[f"matched 1 of {len(candidates)}"],
            )
    return OcrMatchResult(
        matched=False,
        mode="any",
        needle=" | ".join(candidates),
        haystack=haystack_n,
        score=0.0,
        notes=[f"none of {len(candidates)} candidates matched"],
    )
