"""
AI 失敗根因分析：把 failure_bundle / cluster signature / 最近動作 餵給 LLM，
得到結構化 RCA(likely_cause / evidence / next_steps / suggested_fix / confidence)，
再轉成 markdown 報告與 PR comment 用 body。

AI-driven failure triage. Reuses the existing ``failure_bundle``,
``failure_cluster``, ``ai_assist`` and ``pr_comment`` modules:

* Bundle ⇒ structured signal extraction (last N steps, console tail,
  network tail, DOM excerpt, cluster bucket).
* Signals + JSON-only prompt ⇒ ``TriageReport`` dataclass.
* ``render_markdown`` ⇒ human-readable summary.

No LLM provider is bundled — caller registers any
``Callable[[str], str]`` through :mod:`je_web_runner.utils.ai_assist.llm_assist`.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

from je_web_runner.utils.ai_assist.llm_assist import LLMAssistError, _invoke
from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.failure_bundle.bundle import extract_bundle
from je_web_runner.utils.failure_cluster.clustering import normalise_error
from je_web_runner.utils.logging.loggin_instance import web_runner_logger

_EMPTY_LABEL = "<empty>"


class FailureTriageError(WebRunnerException):
    """Raised when triage input is malformed or LLM output cannot be parsed."""


# ---------- signal extraction --------------------------------------------

_DEFAULT_MAX_STEPS = 12
_DEFAULT_MAX_CONSOLE = 30
_DEFAULT_MAX_NETWORK = 20
_DOM_EXCERPT_CHARS = 4000
_ERROR_EXCERPT_CHARS = 1500


@dataclass
class TriageSignals:
    """Signals distilled from a failure bundle, ready for an LLM prompt."""

    test_name: str
    error_repr: str
    error_signature: str
    last_steps: List[Any] = field(default_factory=list)
    console_tail: List[Dict[str, Any]] = field(default_factory=list)
    network_tail: List[Dict[str, Any]] = field(default_factory=list)
    dom_excerpt: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    has_screenshot: bool = False


def _slice_tail(items: Sequence[Any], limit: int) -> List[Any]:
    if not items:
        return []
    return list(items[-limit:])


def _read_bundle_json(files: Dict[str, bytes], rel: str) -> Any:
    raw = files.get(rel)
    if raw is None:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except ValueError:  # UnicodeDecodeError is a subclass of ValueError
        return None


def _read_bundle_text(files: Dict[str, bytes], rel: str) -> str:
    raw = files.get(rel)
    if raw is None:
        return ""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return ""


def extract_signals_from_bundle(
    bundle_path: Union[str, Path],
    *,
    steps: Optional[Sequence[Any]] = None,
    max_steps: int = _DEFAULT_MAX_STEPS,
    max_console: int = _DEFAULT_MAX_CONSOLE,
    max_network: int = _DEFAULT_MAX_NETWORK,
) -> TriageSignals:
    """
    從 failure_bundle zip 抽出 LLM 餵食用的訊號。
    Read a failure bundle written by :class:`FailureBundle`, slice down the
    long-tail signals (console / network / steps) and produce a
    :class:`TriageSignals` payload. ``steps`` is the action history captured
    separately by the runner — pass it in or rely on ``manifest.metadata``.
    """
    extracted = extract_bundle(bundle_path)
    manifest = extracted["manifest"]
    files = extracted["files"]
    if not isinstance(manifest, dict):
        raise FailureTriageError("bundle manifest is not a dict")

    error_repr = str(manifest.get("error_repr") or "")
    console = _read_bundle_json(files, "artifacts/console.json") or []
    network = _read_bundle_json(files, "artifacts/network.json") or []
    dom_html = _read_bundle_text(files, "artifacts/dom.html")
    if steps is None:
        steps = manifest.get("metadata", {}).get("steps") or []
    has_screenshot = any(name.endswith(".png") for name in files)

    return TriageSignals(
        test_name=str(manifest.get("test_name") or ""),
        error_repr=error_repr[:_ERROR_EXCERPT_CHARS],
        error_signature=normalise_error(error_repr),
        last_steps=_slice_tail(list(steps), max_steps),
        console_tail=_slice_tail(console if isinstance(console, list) else [], max_console),
        network_tail=_slice_tail(network if isinstance(network, list) else [], max_network),
        dom_excerpt=dom_html[:_DOM_EXCERPT_CHARS],
        metadata=manifest.get("metadata") or {},
        has_screenshot=has_screenshot,
    )


# ---------- LLM prompt ----------------------------------------------------

_TRIAGE_PROMPT = (
    "You are a senior web-QA engineer doing failure triage. The user has "
    "given you the error message, the last few action steps, console + "
    "network tails, and a DOM excerpt. Identify the single most likely "
    "root cause. Output ONLY a JSON object with these keys (no prose "
    "outside the JSON envelope):\n"
    "  likely_cause:    one-sentence summary\n"
    "  category:        one of {{locator, timing, network, assertion, "
    "environment, data, browser, unknown}}\n"
    "  evidence:        list of short strings citing the specific signals\n"
    "  next_steps:      ordered list of concrete fix attempts\n"
    "  suggested_fix:   one-paragraph code or config change\n"
    "  confidence:      number in [0, 1]\n\n"
    "Test name: {test_name}\n"
    "Error signature: {error_signature}\n"
    "Error message: {error_repr}\n\n"
    "Last steps (most recent last):\n{steps}\n\n"
    "Console tail:\n{console}\n\n"
    "Network tail:\n{network}\n\n"
    "DOM excerpt:\n{dom}\n"
)

_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


@dataclass
class TriageReport:
    """Structured RCA result returned by :func:`triage_failure`."""

    likely_cause: str
    category: str
    evidence: List[str]
    next_steps: List[str]
    suggested_fix: str
    confidence: float
    test_name: str = ""
    error_signature: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


_ALLOWED_CATEGORIES = frozenset({
    "locator", "timing", "network", "assertion",
    "environment", "data", "browser", "unknown",
})


def _parse_triage_payload(text: str) -> Dict[str, Any]:
    match = _JSON_OBJECT_RE.search(text)
    if match is None:
        raise FailureTriageError("LLM did not return a JSON object")
    try:
        payload = json.loads(match.group(0))
    except ValueError as error:
        raise FailureTriageError(f"LLM JSON did not parse: {error}") from error
    if not isinstance(payload, dict):
        raise FailureTriageError(f"LLM payload is not an object: {type(payload).__name__}")
    return payload


def _coerce_str_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        return [value]
    return []


def _coerce_confidence(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    if score < 0.0:
        return 0.0
    if score > 1.0:
        return 1.0
    return score


def _coerce_category(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text if text in _ALLOWED_CATEGORIES else "unknown"


def triage_failure(signals: TriageSignals) -> TriageReport:
    """
    呼叫已註冊的 LLM callable 對失敗訊號做根因分析。
    Send ``signals`` through the LLM registered via
    :func:`set_llm_callable` and parse the JSON response into a
    :class:`TriageReport`. Raises :class:`FailureTriageError` if the response
    is missing required keys or has the wrong shape.
    """
    prompt = _TRIAGE_PROMPT.format(
        test_name=signals.test_name,
        error_signature=signals.error_signature or _EMPTY_LABEL,
        error_repr=signals.error_repr or _EMPTY_LABEL,
        steps=json.dumps(signals.last_steps, ensure_ascii=False, indent=2)[:2500],
        console=json.dumps(signals.console_tail, ensure_ascii=False, indent=2)[:2500],
        network=json.dumps(signals.network_tail, ensure_ascii=False, indent=2)[:2500],
        dom=signals.dom_excerpt[:_DOM_EXCERPT_CHARS] or _EMPTY_LABEL,
    )
    try:
        raw = _invoke(prompt)
    except LLMAssistError as error:
        raise FailureTriageError(str(error)) from error
    payload = _parse_triage_payload(raw)
    missing = {"likely_cause", "evidence", "next_steps", "confidence"} - set(payload)
    if missing:
        raise FailureTriageError(f"LLM payload missing keys: {sorted(missing)}")
    report = TriageReport(
        likely_cause=str(payload.get("likely_cause") or "").strip(),
        category=_coerce_category(payload.get("category")),
        evidence=_coerce_str_list(payload.get("evidence")),
        next_steps=_coerce_str_list(payload.get("next_steps")),
        suggested_fix=str(payload.get("suggested_fix") or "").strip(),
        confidence=_coerce_confidence(payload.get("confidence")),
        test_name=signals.test_name,
        error_signature=signals.error_signature,
    )
    web_runner_logger.info(
        f"triage_failure: test={report.test_name!r} category={report.category} "
        f"confidence={report.confidence:.2f}"
    )
    return report


def triage_bundle(
    bundle_path: Union[str, Path],
    *,
    steps: Optional[Sequence[Any]] = None,
) -> TriageReport:
    """One-shot helper: extract signals + run triage."""
    signals = extract_signals_from_bundle(bundle_path, steps=steps)
    return triage_failure(signals)


# ---------- rendering -----------------------------------------------------

def render_markdown(report: TriageReport, *, heading_level: int = 2) -> str:
    """
    把 TriageReport 印成適合 PR comment / 報告的 markdown。
    Render a triage report as markdown suitable for ``post_or_update_comment``
    or saving as a standalone file.
    """
    h = "#" * max(1, min(heading_level, 6))
    h2 = "#" * max(1, min(heading_level + 1, 6))
    pieces = [
        f"{h} AI Failure Triage — {report.test_name or 'unknown'}",
        "",
        f"- **Likely cause:** {report.likely_cause or '_unspecified_'}",
        f"- **Category:** `{report.category}`",
        f"- **Confidence:** {report.confidence:.0%}",
    ]
    if report.error_signature:
        pieces.append(f"- **Error signature:** `{report.error_signature[:160]}`")
    pieces.append("")
    if report.evidence:
        pieces.append(f"{h2} Evidence")
        pieces.extend(f"- {line}" for line in report.evidence)
        pieces.append("")
    if report.next_steps:
        pieces.append(f"{h2} Next steps")
        pieces.extend(f"{idx}. {line}" for idx, line in enumerate(report.next_steps, 1))
        pieces.append("")
    if report.suggested_fix:
        pieces.append(f"{h2} Suggested fix")
        pieces.append(report.suggested_fix)
        pieces.append("")
    return "\n".join(pieces).rstrip() + "\n"


def save_report(report: TriageReport, output_path: Union[str, Path]) -> Path:
    """Persist a report as JSON next to its bundle for later inspection."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(report.to_dict(), fp, ensure_ascii=False, indent=2)
    web_runner_logger.info(f"save_report: wrote {path}")
    return path
