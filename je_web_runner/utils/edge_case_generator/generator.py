"""
AI 邊界案例產生器:從 passing test 出發,LLM 列出 boundary / 異常 / race / unicode
變體,每個變體都是可執行的 action JSON 草稿,可選擇直接寫入新檔。

Complements :mod:`mutation_testing`:

* mutation_testing **breaks** existing tests to verify they're sensitive.
* edge_case_generator **invents** new tests to widen coverage.

The LLM picks edge-case categories (boundary, unicode, network, timing,
permission, etc.) from a fixed catalogue so output is enumerable and
explainable. Each generated variant ships with a one-line rationale
and the action JSON ready to drop into the suite.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

from je_web_runner.utils.ai_assist.llm_assist import LLMAssistError, _invoke
from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger

_UNNAMED_LABEL = "<unnamed>"


class EdgeCaseGeneratorError(WebRunnerException):
    """Raised when input is malformed or LLM output is unusable."""


class EdgeCaseCategory(str, Enum):
    """Categories the LLM is asked to draw from — keeps output enumerable."""
    BOUNDARY = "boundary"           # min/max numeric, empty string, max-length
    UNICODE = "unicode"             # RTL, emoji, combining marks, zero-width
    NETWORK = "network"             # offline, slow 3G, intermittent 500s
    TIMING = "timing"               # double-click, rapid retry, debounce edge
    PERMISSION = "permission"       # denied geolocation, denied notifications
    AUTH = "auth"                   # expired session, missing CSRF, no cookies
    RACE = "race"                   # two concurrent submits, back-button mid-flow
    INPUT_VALIDATION = "input_validation"  # XSS attempt, SQL-like, control chars
    LOCALE = "locale"               # RTL layout, non-Latin numerals
    A11Y = "a11y"                   # keyboard-only nav, screen-reader path


DEFAULT_CATEGORIES: Sequence[EdgeCaseCategory] = tuple(EdgeCaseCategory)


@dataclass
class EdgeCase:
    """One generated edge-case variant."""

    name: str
    category: EdgeCaseCategory
    rationale: str
    actions: List[Any]
    expected_outcome: str = "fail"  # "fail" | "pass" — what the LLM thinks should happen
    severity: str = "medium"        # "low" | "medium" | "high"

    def to_dict(self) -> Dict[str, Any]:
        out = asdict(self)
        out["category"] = self.category.value
        return out


@dataclass
class EdgeCaseSuite:
    """A bundle of edge-case variants for one source test."""

    source_test_name: str
    cases: List[EdgeCase] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_test_name": self.source_test_name,
            "cases": [c.to_dict() for c in self.cases],
        }


# ---------- prompt -------------------------------------------------------

_GEN_PROMPT = (
    "You are a senior web-QA engineer brainstorming edge cases for a "
    "passing test. Generate exactly {n} variants the original suite "
    "does NOT cover. Output ONLY a JSON object (no prose outside the "
    "envelope) with one key:\n"
    "  cases: list of objects with keys "
    '{{"name": str, "category": str, "rationale": str, '
    '"actions": <action list>, "expected_outcome": "fail" | "pass", '
    '"severity": "low" | "medium" | "high"}}\n\n'
    "Allowed categories: {categories}\n"
    "Test name: {test_name}\n"
    "Original action JSON:\n{actions}\n"
    "Domain context (optional): {context}\n"
)


_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse_payload(text: str) -> Dict[str, Any]:
    match = _JSON_OBJECT_RE.search(text)
    if match is None:
        raise EdgeCaseGeneratorError("LLM did not return a JSON object")
    try:
        payload = json.loads(match.group(0))
    except ValueError as error:
        raise EdgeCaseGeneratorError(f"LLM JSON did not parse: {error}") from error
    if not isinstance(payload, dict):
        raise EdgeCaseGeneratorError(
            f"LLM payload not object: {type(payload).__name__}"
        )
    return payload


def _coerce_category(value: Any) -> EdgeCaseCategory:
    text = str(value or "").strip().lower()
    for member in EdgeCaseCategory:
        if member.value == text:
            return member
    return EdgeCaseCategory.BOUNDARY


def _coerce_severity(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text if text in {"low", "medium", "high"} else "medium"


def _coerce_outcome(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text if text in {"pass", "fail"} else "fail"


def _parse_case(raw: Any) -> Optional[EdgeCase]:
    if not isinstance(raw, dict):
        return None
    actions = raw.get("actions")
    if not isinstance(actions, list):
        return None
    name = str(raw.get("name") or "").strip() or _UNNAMED_LABEL
    return EdgeCase(
        name=name,
        category=_coerce_category(raw.get("category")),
        rationale=str(raw.get("rationale") or "").strip(),
        actions=actions,
        expected_outcome=_coerce_outcome(raw.get("expected_outcome")),
        severity=_coerce_severity(raw.get("severity")),
    )


def generate_edge_cases(
    actions: List[Any],
    *,
    test_name: str = "",
    n: int = 5,
    categories: Sequence[EdgeCaseCategory] = DEFAULT_CATEGORIES,
    context: str = "",
) -> EdgeCaseSuite:
    """
    呼叫 LLM 對 ``actions`` 生 ``n`` 個 edge-case 變體。
    Returns an :class:`EdgeCaseSuite` whose cases are ready to run.
    Cases with malformed shapes are dropped rather than aborting the
    whole batch — partial output is better than none.
    """
    if not isinstance(actions, list):
        raise EdgeCaseGeneratorError(
            f"actions must be a list, got {type(actions).__name__}"
        )
    if n <= 0:
        raise EdgeCaseGeneratorError("n must be positive")
    if not categories:
        categories = DEFAULT_CATEGORIES
    cat_names = ", ".join(c.value for c in categories)
    prompt = _GEN_PROMPT.format(
        n=n,
        categories=cat_names,
        test_name=test_name or _UNNAMED_LABEL,
        actions=json.dumps(actions, ensure_ascii=False, indent=2)[:4500],
        context=context or "<none>",
    )
    try:
        raw = _invoke(prompt)
    except LLMAssistError as error:
        raise EdgeCaseGeneratorError(str(error)) from error
    payload = _parse_payload(raw)
    cases_raw = payload.get("cases")
    if not isinstance(cases_raw, list):
        raise EdgeCaseGeneratorError("LLM payload missing 'cases' list")
    cases: List[EdgeCase] = []
    for item in cases_raw:
        parsed = _parse_case(item)
        if parsed is not None:
            cases.append(parsed)
    web_runner_logger.info(
        f"generate_edge_cases: test={test_name!r} requested={n} parsed={len(cases)}"
    )
    return EdgeCaseSuite(source_test_name=test_name or _UNNAMED_LABEL, cases=cases)


def generate_edge_cases_from_file(
    action_path: Union[str, Path],
    *,
    n: int = 5,
    categories: Sequence[EdgeCaseCategory] = DEFAULT_CATEGORIES,
    context: str = "",
) -> EdgeCaseSuite:
    """Load actions from disk then call :func:`generate_edge_cases`."""
    path = Path(action_path)
    if not path.is_file():
        raise EdgeCaseGeneratorError(f"action file not found: {path}")
    try:
        with open(path, encoding="utf-8") as fp:
            actions = json.load(fp)
    except (OSError, ValueError) as error:
        raise EdgeCaseGeneratorError(f"cannot parse {path}: {error!r}") from error
    if not isinstance(actions, list):
        raise EdgeCaseGeneratorError(f"top-level JSON must be a list: {path}")
    return generate_edge_cases(
        actions,
        test_name=path.stem,
        n=n,
        categories=categories,
        context=context,
    )


# ---------- writing ------------------------------------------------------

def write_suite_to_dir(
    suite: EdgeCaseSuite,
    output_dir: Union[str, Path],
    *,
    filename_prefix: Optional[str] = None,
) -> List[Path]:
    """
    把每個 edge case 寫成一個 action JSON 檔到 ``output_dir``。
    File names are slug-of-name with a numeric prefix so they sort in the
    same order the LLM produced them. Returns the list of written paths.
    """
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    prefix = filename_prefix or _slugify(suite.source_test_name) or "edge"
    written: List[Path] = []
    for idx, case in enumerate(suite.cases, 1):
        slug = _slugify(case.name) or f"case-{idx}"
        path = target / f"{prefix}__{idx:02d}__{slug}.json"
        with open(path, "w", encoding="utf-8") as fp:
            json.dump(case.actions, fp, ensure_ascii=False, indent=2)
        written.append(path)
    web_runner_logger.info(
        f"write_suite_to_dir: wrote {len(written)} edge-case files to {target}"
    )
    return written


_SLUG_RE = re.compile(r"[^A-Za-z0-9_-]+")


def _slugify(value: str) -> str:
    if not value:
        return ""
    cleaned = _SLUG_RE.sub("-", value.strip().lower())
    return cleaned.strip("-")[:60]


# ---------- rendering ---------------------------------------------------

def render_suite_markdown(suite: EdgeCaseSuite) -> str:
    """Markdown view of the suite for PR comments / review."""
    pieces = [
        f"## AI Edge Cases for `{suite.source_test_name}`",
        "",
        f"- **Generated cases:** {len(suite.cases)}",
        "",
    ]
    if not suite.cases:
        pieces.append("_(no cases parsed)_")
        return "\n".join(pieces).rstrip() + "\n"
    pieces.append("| # | Category | Severity | Expects | Name | Rationale |")
    pieces.append("|---|----------|----------|---------|------|-----------|")
    for i, case in enumerate(suite.cases, 1):
        rationale = (case.rationale[:100] + "…") if len(case.rationale) > 100 else case.rationale
        pieces.append(
            f"| {i} | `{case.category.value}` | `{case.severity}` | "
            f"`{case.expected_outcome}` | {case.name} | {rationale} |"
        )
    pieces.append("")
    return "\n".join(pieces).rstrip() + "\n"
