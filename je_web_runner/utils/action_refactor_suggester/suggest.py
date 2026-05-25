"""
Suggest refactors to a WebRunner action JSON list.

Pure-Python rule engine that spots common test-code smells and emits
``Suggestion`` records pointing reviewers at fixes:

* Hard-coded waits (``time.sleep`` / numeric-only ``wait``).
* Brittle XPath (``//div[3]/span[2]``-style positional).
* Duplicated locator strings (extract into a TestObject).
* Repeated click → wait → click bursts (extract a helper).
* Magic-string assertions that look like English copy (use translation key).
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class ActionRefactorSuggesterError(WebRunnerException):
    """Raised on malformed action input."""


class Severity(str, Enum):
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


@dataclass
class Suggestion:
    rule: str
    severity: Severity
    message: str
    step_indexes: List[int] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {**asdict(self), "severity": self.severity.value}


_POSITIONAL_XPATH = re.compile(r"\[\d+\]")
_ENGLISH_SENTENCE = re.compile(r"^[A-Z][\w\s\.,!?:'-]{15,}$")


def _normalize(actions: Sequence[Dict[str, Any]]) -> None:
    if not isinstance(actions, (list, tuple)):
        raise ActionRefactorSuggesterError("actions must be a sequence")
    for i, action in enumerate(actions):
        if not isinstance(action, dict):
            raise ActionRefactorSuggesterError(f"action #{i} is not a dict")


def _hard_sleep_steps(actions: Sequence[Dict[str, Any]]) -> List[int]:
    hits = []
    for i, action in enumerate(actions):
        name = (action.get("action_name") or "").lower()
        if name in ("sleep", "time_sleep"):
            hits.append(i)
        if name == "wait" and isinstance(action.get("value"), (int, float)):
            # numeric-only `wait: 3` is a sleep in disguise
            hits.append(i)
    return hits


def _positional_xpath_steps(actions: Sequence[Dict[str, Any]]) -> List[int]:
    return [
        i for i, a in enumerate(actions)
        if (a.get("by") or "").lower() == "xpath"
        and isinstance(a.get("by_value"), str)
        and _POSITIONAL_XPATH.search(a["by_value"])
    ]


def _duplicated_locators(actions: Sequence[Dict[str, Any]]) -> List[str]:
    locators = [a.get("by_value") for a in actions
                if isinstance(a.get("by_value"), str) and a.get("by_value")]
    counts = Counter(locators)
    return [k for k, v in counts.items() if v >= 3]


def _english_string_assertions(actions: Sequence[Dict[str, Any]]) -> List[int]:
    out = []
    for i, action in enumerate(actions):
        name = (action.get("action_name") or "").lower()
        if name.startswith("assert"):
            expected = action.get("expected") or action.get("value")
            if isinstance(expected, str) and _ENGLISH_SENTENCE.match(expected):
                out.append(i)
    return out


def _click_wait_click_bursts(
    actions: Sequence[Dict[str, Any]],
) -> List[int]:
    out = []
    for i in range(len(actions) - 2):
        names = [
            (actions[i + k].get("action_name") or "").lower()
            for k in range(3)
        ]
        if (names[0].startswith("click")
                and names[1].startswith("wait")
                and names[2].startswith("click")):
            out.append(i)
    return out


def analyze(actions: Sequence[Dict[str, Any]]) -> List[Suggestion]:
    """Run all rules and return suggestions sorted by severity."""
    _normalize(actions)
    out: List[Suggestion] = []
    sleeps = _hard_sleep_steps(actions)
    if sleeps:
        out.append(Suggestion(
            rule="no-hard-sleep", severity=Severity.WARN,
            message="Replace hard sleeps with explicit waits on a condition.",
            step_indexes=sleeps,
        ))
    xpaths = _positional_xpath_steps(actions)
    if xpaths:
        out.append(Suggestion(
            rule="no-positional-xpath", severity=Severity.WARN,
            message="Replace positional XPath with role/text/data-* selector.",
            step_indexes=xpaths,
        ))
    dups = _duplicated_locators(actions)
    if dups:
        out.append(Suggestion(
            rule="extract-duplicated-locator", severity=Severity.INFO,
            message=f"Locator(s) repeated 3+ times: {dups}. Extract a TestObject.",
        ))
    english = _english_string_assertions(actions)
    if english:
        out.append(Suggestion(
            rule="prefer-translation-key", severity=Severity.INFO,
            message="Assertion contains English copy — prefer i18n key for locale safety.",
            step_indexes=english,
        ))
    bursts = _click_wait_click_bursts(actions)
    if bursts:
        out.append(Suggestion(
            rule="extract-helper", severity=Severity.INFO,
            message="Repeated click→wait→click pattern — extract a helper action.",
            step_indexes=bursts,
        ))
    severity_rank = {Severity.ERROR: 0, Severity.WARN: 1, Severity.INFO: 2}
    return sorted(out, key=lambda s: severity_rank[s.severity])


def report_markdown(suggestions: Iterable[Suggestion]) -> str:
    suggestions = list(suggestions)
    if not suggestions:
        return "## Action refactor suggestions\n_No suggestions — looks clean._"
    lines = ["## Action refactor suggestions"]
    for s in suggestions:
        marker = {"error": "❌", "warn": "⚠️", "info": "ℹ️"}.get(s.severity.value, "•")
        lines.append(f"- {marker} **{s.rule}** — {s.message}")
        if s.step_indexes:
            lines.append(f"  at steps: {s.step_indexes}")
    return "\n".join(lines)


def assert_no_warns_or_errors(suggestions: Iterable[Suggestion]) -> None:
    bad = [s for s in suggestions
           if s.severity in (Severity.WARN, Severity.ERROR)]
    if bad:
        rules = [s.rule for s in bad]
        raise ActionRefactorSuggesterError(
            f"action script has warnings/errors: {rules}"
        )
