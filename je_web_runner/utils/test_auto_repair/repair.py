"""
AI 測試自動維修:把失敗訊號 + git diff + 既有 action JSON 餵 LLM,
產出修補後的 action list 草稿,可選擇直接寫回檔案。

Builds on :mod:`failure_triage` (already extracts signals from a failure
bundle) and :mod:`locator_health` (which already knows how to suggest
locator upgrades). What this module adds:

* **git diff context** — the recent code change is often the smoking
  gun; we read ``git diff <since>..HEAD`` and trim to budget.
* **LLM repair prompt** — JSON-only contract that returns a fully
  rewritten action list plus a per-change explanation.
* **apply** — write the repaired list back to the action JSON, optionally
  to a side file for human review first.

The LLM caller is the one registered via
:func:`je_web_runner.utils.ai_assist.llm_assist.set_llm_callable`.
"""
from __future__ import annotations

import json
import re
import subprocess  # nosec B404 — used for `git diff` invocation, args are statically composed
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

from je_web_runner.utils.ai_assist.llm_assist import LLMAssistError, _invoke
from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.failure_triage.triage import (
    TriageSignals,
    extract_signals_from_bundle,
)
from je_web_runner.utils.logging.loggin_instance import web_runner_logger

_EMPTY_LABEL = "<empty>"


class TestAutoRepairError(WebRunnerException):
    """Raised when repair input, LLM output, or file I/O is invalid."""

    __test__ = False  # domain exception, not a pytest test class


# ---------- git diff -----------------------------------------------------

_DEFAULT_DIFF_MAX_CHARS = 6000


def collect_git_diff(
    repo_dir: str | Path = ".",
    *,
    since_ref: str = "HEAD~1",
    paths: Sequence[str] | None = None,
    max_chars: int = _DEFAULT_DIFF_MAX_CHARS,
    runner: Callable[..., subprocess.CompletedProcess] | None = None,
) -> str:
    """
    讀 ``git diff <since_ref>..HEAD``(可選擇限定 paths),截到 ``max_chars``。
    Returns the diff text or empty string if git is unavailable. ``runner``
    lets tests substitute a fake ``subprocess.run``.
    """
    cmd: list[str] = ["git", "-C", str(repo_dir), "diff", f"{since_ref}..HEAD", "--unified=2"]
    if paths:
        cmd.append("--")
        cmd.extend(str(p) for p in paths)
    runner = runner or subprocess.run
    try:
        result = runner(
            cmd, capture_output=True, text=True, timeout=15.0, check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        web_runner_logger.warning(f"collect_git_diff: git invocation failed: {error!r}")
        return ""
    if result.returncode != 0:
        web_runner_logger.info(
            f"collect_git_diff: git exited {result.returncode}: {result.stderr[:200]}"
        )
        return ""
    text = result.stdout or ""
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n… (truncated {len(result.stdout) - max_chars} chars)"
    return text


# ---------- repair model -----------------------------------------------

@dataclass
class RepairPlan:
    """Structured repair output from the LLM."""

    summary: str
    confidence: float
    repaired_actions: list[Any]
    changes: list[dict[str, Any]] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_REPAIR_PROMPT = (
    "You are a senior web-QA engineer doing automated test repair. The "
    "test below was passing before the latest code change and is now "
    "failing. Produce a repaired version of the action list. Output "
    "ONLY a JSON object (no prose outside the envelope) with these keys:\n"
    "  summary:           one-sentence rationale for the repair\n"
    "  confidence:        number in [0,1]\n"
    "  repaired_actions:  the full corrected action list (same shape)\n"
    "  changes:           list of objects "
    '{{"index": int, "kind": "locator|timeout|removal|insertion|other", '
    '"before": <original>, "after": <new>, "why": "..."}}\n'
    "  risks:             list of caveats / things to double-check\n\n"
    "Failing test: {test_name}\n"
    "Error signature: {error_signature}\n"
    "Error: {error_repr}\n\n"
    "Recent code diff:\n{diff}\n\n"
    "Original action JSON:\n{actions}\n\n"
    "Last runtime steps:\n{steps}\n\n"
    "DOM excerpt:\n{dom}\n"
)


_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse_payload(text: str) -> dict[str, Any]:
    match = _JSON_OBJECT_RE.search(text)
    if match is None:
        raise TestAutoRepairError("LLM did not return a JSON object")
    try:
        payload = json.loads(match.group(0))
    except ValueError as error:
        raise TestAutoRepairError(f"LLM JSON did not parse: {error}") from error
    if not isinstance(payload, dict):
        raise TestAutoRepairError(
            f"LLM payload is not an object: {type(payload).__name__}"
        )
    return payload


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


def _coerce_change_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    out: list[dict[str, Any]] = []
    for entry in value:
        if isinstance(entry, dict):
            out.append(entry)
    return out


def _coerce_str_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        return [value]
    return []


def propose_repair(
    actions: list[Any],
    signals: TriageSignals,
    *,
    diff_text: str = "",
) -> RepairPlan:
    """
    呼叫 LLM 提出一份 RepairPlan(不寫檔)。
    Returns a :class:`RepairPlan` with a fully-rewritten action list and
    per-change explanations. Caller decides whether to apply the result.
    """
    if not isinstance(actions, list):
        raise TestAutoRepairError(
            f"actions must be a list, got {type(actions).__name__}"
        )
    prompt = _REPAIR_PROMPT.format(
        test_name=signals.test_name or "unknown",
        error_signature=signals.error_signature or _EMPTY_LABEL,
        error_repr=signals.error_repr or _EMPTY_LABEL,
        diff=diff_text or "<no diff available>",
        actions=json.dumps(actions, ensure_ascii=False, indent=2)[:5000],
        steps=json.dumps(signals.last_steps, ensure_ascii=False, indent=2)[:2500],
        dom=signals.dom_excerpt[:3500] or _EMPTY_LABEL,
    )
    try:
        raw = _invoke(prompt)
    except LLMAssistError as error:
        raise TestAutoRepairError(str(error)) from error
    payload = _parse_payload(raw)
    if "repaired_actions" not in payload:
        raise TestAutoRepairError("LLM payload missing 'repaired_actions'")
    repaired = payload.get("repaired_actions")
    if not isinstance(repaired, list):
        raise TestAutoRepairError(
            f"'repaired_actions' must be a list, got {type(repaired).__name__}"
        )
    plan = RepairPlan(
        summary=str(payload.get("summary") or "").strip(),
        confidence=_coerce_confidence(payload.get("confidence")),
        repaired_actions=repaired,
        changes=_coerce_change_list(payload.get("changes")),
        risks=_coerce_str_list(payload.get("risks")),
    )
    web_runner_logger.info(
        f"propose_repair: test={signals.test_name!r} confidence={plan.confidence:.2f} "
        f"changes={len(plan.changes)}"
    )
    return plan


def repair_from_bundle(
    action_path: str | Path,
    bundle_path: str | Path,
    *,
    repo_dir: str | Path = ".",
    since_ref: str = "HEAD~1",
    git_runner: Callable[..., subprocess.CompletedProcess] | None = None,
) -> RepairPlan:
    """
    One-shot:讀 action 檔 + failure bundle + git diff,回傳 RepairPlan。
    """
    actions = _load_actions(action_path)
    signals = extract_signals_from_bundle(bundle_path)
    diff_text = collect_git_diff(repo_dir, since_ref=since_ref, runner=git_runner)
    return propose_repair(actions, signals, diff_text=diff_text)


def _load_actions(action_path: str | Path) -> list[Any]:
    path = Path(action_path)
    if not path.is_file():
        raise TestAutoRepairError(f"action file not found: {path}")
    try:
        with open(path, encoding="utf-8") as fp:
            payload = json.load(fp)
    except (OSError, ValueError) as error:
        raise TestAutoRepairError(f"cannot parse {path}: {error!r}") from error
    if not isinstance(payload, list):
        raise TestAutoRepairError(f"top-level JSON must be a list: {path}")
    return payload


# ---------- apply / write back ------------------------------------------

def apply_repair(
    action_path: str | Path,
    plan: RepairPlan,
    *,
    output_path: str | Path | None = None,
    min_confidence: float = 0.5,
) -> Path:
    """
    把 plan.repaired_actions 寫入 ``output_path`` (預設 ``<action>.repaired.json``)。
    Raises :class:`TestAutoRepairError` when ``plan.confidence`` is below
    ``min_confidence`` — caller can lower the threshold if they're OK
    with a draft they review by hand. The original file is **never**
    overwritten unless ``output_path`` is explicitly set to it.
    """
    if plan.confidence < min_confidence:
        raise TestAutoRepairError(
            f"confidence {plan.confidence:.2f} below minimum {min_confidence:.2f}; "
            "review the plan manually before applying"
        )
    src = Path(action_path)
    if output_path is None:
        target = src.with_suffix(src.suffix + ".repaired.json")
    else:
        target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8") as fp:
        json.dump(plan.repaired_actions, fp, ensure_ascii=False, indent=2)
    web_runner_logger.info(f"apply_repair: wrote {target}")
    return target


# ---------- rendering ---------------------------------------------------

def render_repair_markdown(plan: RepairPlan, *, heading_level: int = 2) -> str:
    """Markdown view of the plan, intended for PR comments."""
    h = "#" * max(1, min(heading_level, 6))
    h2 = "#" * max(1, min(heading_level + 1, 6))
    pieces = [
        f"{h} AI Test Auto-Repair",
        "",
        f"- **Summary:** {plan.summary or '_unspecified_'}",
        f"- **Confidence:** {plan.confidence:.0%}",
        f"- **Changes:** {len(plan.changes)}",
        "",
    ]
    if plan.changes:
        pieces.append(f"{h2} Changes")
        pieces.append("| # | Idx | Kind | Why |")
        pieces.append("|---|-----|------|-----|")
        for i, change in enumerate(plan.changes, 1):
            pieces.append(
                f"| {i} | {change.get('index', '—')} | "
                f"`{change.get('kind', 'other')}` | {change.get('why', '')} |"
            )
        pieces.append("")
    if plan.risks:
        pieces.append(f"{h2} Risks / things to double-check")
        pieces.extend(f"- {r}" for r in plan.risks)
        pieces.append("")
    return "\n".join(pieces).rstrip() + "\n"
