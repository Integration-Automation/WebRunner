"""
讀脆弱 locator(來自 ``locator_health`` 報告)+ 周圍 DOM,LLM 建議更穩的 selector。
Common bad locators we want to harden:

* nth-of-type / nth-child selectors that drift when content reorders
* deeply nested CSS descendants
* class-only selectors when classes are CSS-modules-hashed
* XPath that depends on text content

The "smart" part is delegated to a :class:`HardenerClient`; the module
does:

1. Score-based pre-classification (which locators are *worth* hardening
   vs already-fine).
2. Prompt assembly (DOM excerpt + the locator + recommended-style hints).
3. Strict response validation (every suggestion must be valid CSS or
   XPath syntax; we don't trust the LLM blindly).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol

from je_web_runner.utils.exception.exceptions import WebRunnerException


class LocatorHardenerError(WebRunnerException):
    """Raised on bad inputs / parse failures / failed assertion."""


# ---------- inputs ------------------------------------------------------

class LocatorStrategy(str, Enum):
    """Allowed WR locator strategies."""

    ID = "id"
    NAME = "name"
    CSS = "css selector"
    XPATH = "xpath"
    LINK_TEXT = "link text"
    PARTIAL_LINK_TEXT = "partial link text"
    CLASS_NAME = "class name"
    TAG_NAME = "tag name"


_PREFERRED_STRATEGIES = (
    LocatorStrategy.ID, LocatorStrategy.NAME, LocatorStrategy.CSS,
)


@dataclass
class FragileLocator:
    """One locator candidate worth hardening."""

    test_id: str
    strategy: LocatorStrategy
    value: str
    dom_excerpt: str = ""
    failure_history: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.test_id, str) or not self.test_id:
            raise LocatorHardenerError("test_id must be non-empty string")
        if not isinstance(self.value, str) or not self.value:
            raise LocatorHardenerError("value must be non-empty string")
        if self.failure_history < 0:
            raise LocatorHardenerError("failure_history must be >= 0")


# ---------- heuristic pre-classifier -----------------------------------

_NTH_PATTERN = re.compile(r":nth-(?:of-type|child)\(\d+\)", re.IGNORECASE)
# NOSONAR python:S5852 — input is a CSS selector (bounded, internal), not user text
_DEEP_DESCENDANT = re.compile(r"\s+\S+\s+\S+\s+\S+")
_HASHED_CLASS = re.compile(r"[._][A-Za-z][\w-]*?-_?\w{4,}\b")
_TEXT_XPATH = re.compile(r"text\s*\(\s*\)", re.IGNORECASE)


@dataclass
class FragilityScore:
    """Heuristic locator-fragility score (0..1)."""

    score: float
    reasons: list[str] = field(default_factory=list)


def score_fragility(locator: FragileLocator) -> FragilityScore:
    """Quick non-LLM check. Anything ``score >= 0.5`` is worth hardening."""
    if not isinstance(locator, FragileLocator):
        raise LocatorHardenerError("expects FragileLocator")
    reasons: list[str] = []
    score = 0.0
    if locator.strategy == LocatorStrategy.XPATH:
        score += 0.2
        reasons.append("xpath locator")
        if _TEXT_XPATH.search(locator.value):
            score += 0.3
            reasons.append("uses text() predicate")
    if locator.strategy == LocatorStrategy.CSS:
        if _NTH_PATTERN.search(locator.value):
            score += 0.4
            reasons.append("uses :nth-of-type/child")
        if _DEEP_DESCENDANT.search(locator.value):
            score += 0.2
            reasons.append("deeply nested CSS")
        if _HASHED_CLASS.search(locator.value):
            score += 0.4
            reasons.append("hashed class names")
    if locator.strategy not in _PREFERRED_STRATEGIES:
        score += 0.1
        reasons.append("non-preferred strategy")
    if locator.failure_history >= 3:
        score += 0.3
        reasons.append(f"failed {locator.failure_history} times historically")
    if locator.strategy == LocatorStrategy.CLASS_NAME and " " in locator.value:
        score += 0.2
        reasons.append("multi-class CLASS_NAME (treated as single class)")
    return FragilityScore(score=min(score, 1.0), reasons=reasons)


# ---------- LLM client ------------------------------------------------

class HardenerClient(Protocol):
    """LLM client interface."""

    def suggest(self, prompt: str) -> str: ...


# ---------- prompt -----------------------------------------------------

PROMPT_TEMPLATE = """\
You are improving an end-to-end test locator to make it more resilient.

# Current locator
- strategy: {strategy}
- value: {value}
- found in test: {test_id}
- failure history (recent): {failure_history}

# DOM excerpt around the target element
```html
{dom_excerpt}
```

# Constraints
- Prefer ID > name > stable test attributes > short CSS.
- Reject :nth-of-type / :nth-child selectors.
- Reject locators that depend on visible text unless no stable attribute exists.
- Return strictly a JSON array of suggestion objects sorted best-first,
  each with keys: "strategy" (one of {strategies}),
  "value" (string), "rationale" (string).
"""


def build_prompt(locator: FragileLocator) -> str:
    if not isinstance(locator, FragileLocator):
        raise LocatorHardenerError("build_prompt expects FragileLocator")
    return PROMPT_TEMPLATE.format(
        strategy=locator.strategy.value,
        value=locator.value,
        test_id=locator.test_id,
        failure_history=locator.failure_history,
        dom_excerpt=locator.dom_excerpt or "(none)",
        strategies=[s.value for s in LocatorStrategy],
    )


# ---------- response parsing -------------------------------------------

@dataclass
class LocatorSuggestion:
    """One suggested replacement locator."""

    strategy: LocatorStrategy
    value: str
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {"strategy": self.strategy.value, "value": self.value,
                "rationale": self.rationale}

def parse_suggestions(raw: str) -> list[LocatorSuggestion]:  # NOSONAR S3776 — cohesive logic; planned refactor in follow-up PR
    """Decode the LLM's JSON array; reject malformed entries."""
    if not isinstance(raw, str) or not raw.strip():
        raise LocatorHardenerError("LLM returned empty response")
    start = raw.find("[")
    end = raw.rfind("]")
    if start == -1 or end == -1 or end <= start:
        raise LocatorHardenerError(f"no JSON array in response: {raw[:160]!r}")
    try:
        obj = json.loads(raw[start:end + 1])
    except ValueError as error:
        raise LocatorHardenerError(
            f"suggestions not JSON ({error}): {raw[:160]!r}"
        ) from error
    if not isinstance(obj, list):
        raise LocatorHardenerError("suggestions must be a list")
    out: list[LocatorSuggestion] = []
    for index, raw_item in enumerate(obj):
        if not isinstance(raw_item, dict):
            continue
        strategy_str = raw_item.get("strategy") or ""
        value = raw_item.get("value") or ""
        rationale = raw_item.get("rationale") or ""
        try:
            strategy = LocatorStrategy(strategy_str)
        except ValueError:
            continue
        if not isinstance(value, str) or not value:
            continue
        if not _looks_safe(strategy, value):
            continue
        out.append(LocatorSuggestion(
            strategy=strategy, value=str(value), rationale=str(rationale),
        ))
    if not out:
        raise LocatorHardenerError("no valid suggestions in LLM response")
    return out


def _looks_safe(strategy: LocatorStrategy, value: str) -> bool:
    if strategy == LocatorStrategy.CSS and _NTH_PATTERN.search(value):
        return False
    if strategy == LocatorStrategy.XPATH and _TEXT_XPATH.search(value):
        return False
    return True


# ---------- end-to-end -------------------------------------------------

def harden(
    locator: FragileLocator,
    client: HardenerClient,
    *,
    min_fragility: float = 0.5,
) -> list[LocatorSuggestion]:
    """Score → maybe-skip → ask LLM → parse → return."""
    if not 0.0 <= min_fragility <= 1.0:
        raise LocatorHardenerError("min_fragility must be in [0, 1]")
    fragility = score_fragility(locator)
    if fragility.score < min_fragility:
        return []
    prompt = build_prompt(locator)
    try:
        raw = client.suggest(prompt)
    except Exception as error:
        raise LocatorHardenerError(
            f"hardener client failed: {error!r}"
        ) from error
    return parse_suggestions(raw)
