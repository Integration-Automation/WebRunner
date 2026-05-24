"""
給 vision LLM 看截圖 + 問題,解析「對嗎?」的結構化回答。
Use cases that snapshot-diff can't catch on its own:

* "Is the error toast styled like the design system spec?"
* "Does the chart axis labelling make sense?"
* "Are there any visual artifacts (cropped text, overlapping elements)?"

The LLM call is hidden behind :class:`VisionClient`, so this module
stays unit-testable without a model. Production code plugs in Claude
Vision / GPT-4o / a local VLM.

Response handling is defensive: the JSON envelope is required, but
malformed responses degrade to a clear failure rather than a silent
pass.
"""
from __future__ import annotations

import base64
import json
import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Protocol, Sequence, Union

from je_web_runner.utils.exception.exceptions import WebRunnerException


class MultimodalQaError(WebRunnerException):
    """Raised on bad image input, client failure, or unparseable response."""


# ---------- enums -------------------------------------------------------

class Verdict(str, Enum):
    """Final outcome of a single Q."""

    PASS = "pass"  # nosec B105 — verdict label, not a credential
    FAIL = "fail"
    UNCERTAIN = "uncertain"


# ---------- data --------------------------------------------------------

@dataclass
class QaRequest:
    """One screenshot + question to send to the LLM."""

    image_bytes: bytes
    question: str
    rubric: List[str] = field(default_factory=list)
    image_label: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.image_bytes, (bytes, bytearray)):
            raise MultimodalQaError(
                f"image_bytes must be bytes, got {type(self.image_bytes).__name__}"
            )
        if not self.image_bytes:
            raise MultimodalQaError("image_bytes must be non-empty")
        if not isinstance(self.question, str) or not self.question.strip():
            raise MultimodalQaError("question must be a non-empty string")

    def b64_image(self) -> str:
        return base64.b64encode(bytes(self.image_bytes)).decode("ascii")


@dataclass
class QaResponse:
    """Parsed vision-LLM response."""

    verdict: Verdict
    confidence: float
    rationale: str
    issues: List[str] = field(default_factory=list)
    raw: str = ""

    def is_pass(self) -> bool:
        return self.verdict == Verdict.PASS

    def to_dict(self) -> Dict[str, Any]:
        return {**asdict(self), "verdict": self.verdict.value}


# ---------- client protocol --------------------------------------------

class VisionClient(Protocol):
    """LLM client interface."""

    def ask(self, prompt: str, image_b64: str) -> str: ...


# ---------- prompt -----------------------------------------------------

def build_prompt(request: QaRequest) -> str:
    """Render a deterministic prompt the vision model will see."""
    parts: List[str] = [
        "You are reviewing a UI screenshot. Answer the question strictly.",
        "Respond with ONLY a JSON object on a single line with keys:",
        '  "verdict": one of "pass" | "fail" | "uncertain"',
        '  "confidence": number in [0, 1]',
        '  "rationale": short string explaining the verdict',
        '  "issues": list of strings, one per concrete issue (empty if none)',
        "",
        f"Question: {request.question.strip()}",
    ]
    if request.rubric:
        parts.append("Rubric (each item must be true for a 'pass'):")
        parts.extend(f"- {item}" for item in request.rubric)
    return "\n".join(parts)


# ---------- parsing ----------------------------------------------------

_JSON_LINE_RE = re.compile(r"\{.*\}", re.DOTALL)


def parse_response(raw: str) -> QaResponse:
    """Parse the model's text into a :class:`QaResponse`."""
    if not isinstance(raw, str) or not raw.strip():
        raise MultimodalQaError("model response was empty")
    match = _JSON_LINE_RE.search(raw)
    if not match:
        raise MultimodalQaError(f"no JSON object in response: {raw[:200]!r}")
    try:
        obj = json.loads(match.group(0))
    except ValueError as error:
        raise MultimodalQaError(
            f"response was not valid JSON ({error}): {raw[:200]!r}"
        ) from error
    if not isinstance(obj, dict):
        raise MultimodalQaError(f"response JSON must be an object, got {type(obj).__name__}")
    try:
        verdict = Verdict(str(obj.get("verdict") or "").lower())
    except ValueError as error:
        raise MultimodalQaError(f"unknown verdict in response: {error}") from error
    confidence_raw = obj.get("confidence")
    if not isinstance(confidence_raw, (int, float)):
        raise MultimodalQaError("response missing numeric 'confidence'")
    confidence = max(0.0, min(1.0, float(confidence_raw)))
    issues_raw = obj.get("issues") or []
    if not isinstance(issues_raw, list):
        raise MultimodalQaError("response 'issues' must be a list")
    return QaResponse(
        verdict=verdict,
        confidence=confidence,
        rationale=str(obj.get("rationale") or ""),
        issues=[str(i) for i in issues_raw],
        raw=raw,
    )


# ---------- ask --------------------------------------------------------

def ask(
    request: QaRequest,
    client: VisionClient,
) -> QaResponse:
    """Build prompt → ask client → parse → return :class:`QaResponse`."""
    prompt = build_prompt(request)
    try:
        raw = client.ask(prompt, request.b64_image())
    except Exception as error:
        raise MultimodalQaError(f"vision client failed: {error!r}") from error
    return parse_response(raw)


def ask_path(
    path: Union[str, Path],
    question: str,
    client: VisionClient,
    *,
    rubric: Sequence[str] = (),
) -> QaResponse:
    """Convenience: load an image off disk and call :func:`ask`."""
    p = Path(path)
    if not p.exists():
        raise MultimodalQaError(f"image not found: {p}")
    request = QaRequest(
        image_bytes=p.read_bytes(),
        question=question,
        rubric=list(rubric),
        image_label=str(p),
    )
    return ask(request, client)


# ---------- assertion --------------------------------------------------

def assert_passes(
    response: QaResponse,
    *,
    min_confidence: float = 0.6,
) -> None:
    """Raise unless the response is a confident pass."""
    if not isinstance(response, QaResponse):
        raise MultimodalQaError("assert_passes expects QaResponse")
    if not 0.0 <= min_confidence <= 1.0:
        raise MultimodalQaError("min_confidence must be in [0, 1]")
    if response.verdict != Verdict.PASS:
        joined = ", ".join(response.issues) or response.rationale
        raise MultimodalQaError(
            f"verdict={response.verdict.value} (confidence={response.confidence:.2f}): {joined}"
        )
    if response.confidence < min_confidence:
        raise MultimodalQaError(
            f"verdict=pass but confidence {response.confidence:.2f} "
            f"< min {min_confidence:.2f}: {response.rationale}"
        )
