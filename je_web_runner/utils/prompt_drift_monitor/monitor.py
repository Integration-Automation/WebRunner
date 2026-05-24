"""
追蹤 app 內 LLM 輸出隨時間飄移。
應用情境:你的 app 自己有 LLM 功能(客服 bot、文章摘要、智能搜尋),你要監測它的回答品質是否隨時間下滑。
Two complementary signals:

* **Embedding similarity to a frozen baseline** — drift > threshold flags
  the run for review.
* **Lexical anchors** — list of phrases that *must* appear (a brand name,
  a disclaimer) or *must not* appear (a forbidden competitor name, a
  banned topic). Lexical checks complement embeddings: drift below the
  similarity threshold still fails if the disclaimer disappeared.

State is stored as a tiny JSON baseline file so a CI job can compare
today's output against last week's snapshot without a database.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Union

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class PromptDriftError(WebRunnerException):
    """Raised on malformed baseline / embeddings / config."""


Embedder = Callable[[str], Sequence[float]]
"""Callable: text → embedding vector."""


# ---------- baseline ----------------------------------------------------

@dataclass
class BaselineSample:
    """One frozen reference answer."""

    prompt_id: str
    prompt: str
    answer: str
    embedding: List[float]
    must_include: List[str] = field(default_factory=list)
    must_exclude: List[str] = field(default_factory=list)
    captured_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Baseline:
    """Set of frozen reference samples, persisted as JSON."""

    samples: List[BaselineSample] = field(default_factory=list)
    captured_at: str = ""

    def by_id(self) -> Dict[str, BaselineSample]:
        return {s.prompt_id: s for s in self.samples}


def capture_baseline(
    prompts: Sequence[Dict[str, Any]],
    embedder: Embedder,
    answerer: Callable[[str], str],
) -> Baseline:
    """
    Walk ``prompts`` (each ``{id, prompt, must_include?, must_exclude?}``),
    ask ``answerer`` for the current answer, embed it, package as Baseline.
    """
    if not prompts:
        raise PromptDriftError("prompts must be non-empty")
    samples: List[BaselineSample] = []
    now = datetime.now(tz=timezone.utc).isoformat(timespec="seconds")
    for raw in prompts:
        if not isinstance(raw, dict):
            raise PromptDriftError("each prompt must be a dict")
        prompt_id = str(raw.get("id") or "").strip()
        prompt_text = str(raw.get("prompt") or "").strip()
        if not prompt_id or not prompt_text:
            raise PromptDriftError("each prompt needs non-empty 'id' and 'prompt'")
        try:
            answer = str(answerer(prompt_text))
        except Exception as error:
            raise PromptDriftError(
                f"answerer failed for {prompt_id!r}: {error!r}"
            ) from error
        vec = _embed_or_raise(embedder, answer, label=prompt_id)
        samples.append(BaselineSample(
            prompt_id=prompt_id,
            prompt=prompt_text,
            answer=answer,
            embedding=list(vec),
            must_include=[str(v) for v in raw.get("must_include") or []],
            must_exclude=[str(v) for v in raw.get("must_exclude") or []],
            captured_at=now,
        ))
    return Baseline(samples=samples, captured_at=now)


def save_baseline(baseline: Baseline, path: Union[str, Path]) -> Path:
    """Persist baseline to JSON."""
    if not isinstance(baseline, Baseline):
        raise PromptDriftError("save_baseline expects Baseline")
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "captured_at": baseline.captured_at,
        "samples": [s.to_dict() for s in baseline.samples],
    }
    with open(p, "w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False, indent=2)
    return p


def load_baseline(path: Union[str, Path]) -> Baseline:
    """Read baseline JSON back into a :class:`Baseline`."""
    p = Path(path)
    if not p.exists():
        raise PromptDriftError(f"baseline file not found: {p}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except ValueError as error:
        raise PromptDriftError(f"baseline file invalid: {error}") from error
    if not isinstance(data, dict) or not isinstance(data.get("samples"), list):
        raise PromptDriftError("baseline JSON missing 'samples' list")
    samples: List[BaselineSample] = []
    for raw in data["samples"]:
        if not isinstance(raw, dict):
            continue
        try:
            samples.append(BaselineSample(
                prompt_id=str(raw["prompt_id"]),
                prompt=str(raw["prompt"]),
                answer=str(raw["answer"]),
                embedding=[float(x) for x in raw["embedding"]],
                must_include=[str(v) for v in raw.get("must_include") or []],
                must_exclude=[str(v) for v in raw.get("must_exclude") or []],
                captured_at=str(raw.get("captured_at") or ""),
            ))
        except (KeyError, TypeError, ValueError) as error:
            raise PromptDriftError(f"malformed sample: {error}") from error
    return Baseline(
        samples=samples,
        captured_at=str(data.get("captured_at") or ""),
    )


# ---------- monitoring --------------------------------------------------

@dataclass
class DriftFinding:
    """Per-prompt drift verdict."""

    prompt_id: str
    similarity: float
    drifted: bool
    missing_required: List[str] = field(default_factory=list)
    forbidden_present: List[str] = field(default_factory=list)
    current_answer: str = ""


@dataclass
class DriftReport:
    """Roll-up returned by :func:`check_drift`."""

    threshold: float
    findings: List[DriftFinding] = field(default_factory=list)

    def drifted_findings(self) -> List[DriftFinding]:
        return [f for f in self.findings
                if f.drifted or f.missing_required or f.forbidden_present]

    def passed(self) -> bool:
        return not self.drifted_findings()


def check_drift(
    baseline: Baseline,
    embedder: Embedder,
    answerer: Callable[[str], str],
    *,
    similarity_threshold: float = 0.85,
) -> DriftReport:
    """
    For each baseline sample, ask the current model, embed, compare.
    Any sample below ``similarity_threshold`` or missing/including a
    forbidden anchor is reported as drifted.
    """
    if not isinstance(baseline, Baseline):
        raise PromptDriftError("check_drift expects Baseline")
    if not 0.0 < similarity_threshold <= 1.0:
        raise PromptDriftError("similarity_threshold must be in (0, 1]")
    report = DriftReport(threshold=similarity_threshold)
    for sample in baseline.samples:
        try:
            current = str(answerer(sample.prompt))
        except Exception as error:
            raise PromptDriftError(
                f"answerer failed for {sample.prompt_id!r}: {error!r}"
            ) from error
        vec = _embed_or_raise(embedder, current, label=sample.prompt_id)
        similarity = _cosine(sample.embedding, list(vec))
        missing = [phrase for phrase in sample.must_include
                   if phrase and phrase.lower() not in current.lower()]
        forbidden = [phrase for phrase in sample.must_exclude
                     if phrase and phrase.lower() in current.lower()]
        drifted = similarity < similarity_threshold
        report.findings.append(DriftFinding(
            prompt_id=sample.prompt_id,
            similarity=round(similarity, 4),
            drifted=drifted,
            missing_required=missing,
            forbidden_present=forbidden,
            current_answer=current,
        ))
        if drifted or missing or forbidden:
            web_runner_logger.warning(
                f"prompt_drift: {sample.prompt_id} sim={similarity:.3f} "
                f"missing={missing} forbidden={forbidden}"
            )
    return report


# ---------- helpers -----------------------------------------------------

def assert_no_drift(report: DriftReport) -> None:
    """Raise unless the report has no drifted findings."""
    if not isinstance(report, DriftReport):
        raise PromptDriftError("assert_no_drift expects DriftReport")
    if report.passed():
        return
    parts = [
        f"{f.prompt_id}(sim={f.similarity:.2f})"
        for f in report.drifted_findings()[:5]
    ]
    more = (
        ""
        if len(report.drifted_findings()) <= 5
        else f" (+{len(report.drifted_findings()) - 5})"
    )
    raise PromptDriftError(f"prompt drift detected: {', '.join(parts)}{more}")


def _embed_or_raise(embedder: Embedder, text: str, *, label: str) -> Sequence[float]:
    try:
        vec = embedder(text)
    except Exception as error:
        raise PromptDriftError(
            f"embedder failed for {label!r}: {error!r}"
        ) from error
    if not isinstance(vec, (list, tuple)) or not vec:
        raise PromptDriftError(f"embedder returned bad vector for {label!r}: {vec!r}")
    return vec


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b) or not a:
        raise PromptDriftError("embeddings must be non-empty and equal-length")
    dot = sum(float(x) * float(y) for x, y in zip(a, b))
    norm_a = math.sqrt(sum(float(x) * float(x) for x in a))
    norm_b = math.sqrt(sum(float(x) * float(x) for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
