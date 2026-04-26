"""
Locator 脆弱度評分：給每個 locator 一個 0–100 分，越高越穩定。
Locator strength scorer. Heuristically grades a Selenium-style locator on
a 0–100 scale: ID > test-id > stable CSS > class chain > deep XPath > text-only.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

from je_web_runner.utils.exception.exceptions import WebRunnerException


class LocatorStrengthError(WebRunnerException):
    """Raised when a locator definition can't be evaluated."""


@dataclass
class LocatorScore:
    strategy: str
    value: str
    score: int
    reasons: List[str]


_TEST_ID_HINTS = ("data-testid", "data-test", "data-qa", "data-cy")
_NTH_PATTERN = re.compile(r":nth-child|:nth-of-type")
_DYNAMIC_CLASS_PATTERN = re.compile(r"\b[a-z]+-[A-Za-z0-9]{6,}\b")


def _score_id(value: str) -> Tuple[int, List[str]]:
    if not value:
        return 0, ["empty id"]
    if any(ch.isdigit() for ch in value) and len(value) >= 12:
        return 60, ["likely auto-generated id"]
    return 95, []


def _score_test_id_attr(value: str) -> Tuple[int, List[str]]:
    if any(hint in value for hint in _TEST_ID_HINTS):
        return 90, []
    return 75, ["no data-test* attribute"]


def _score_css(value: str) -> Tuple[int, List[str]]:
    reasons: List[str] = []
    score = 75
    depth = value.count(">") + value.count(" ")
    if depth >= 4:
        score -= 15
        reasons.append(f"deep selector chain ({depth} hops)")
    if _NTH_PATTERN.search(value):
        score -= 20
        reasons.append("uses nth-child / nth-of-type")
    if _DYNAMIC_CLASS_PATTERN.search(value):
        score -= 10
        reasons.append("class name looks generated")
    if any(hint in value for hint in _TEST_ID_HINTS):
        return 90, ["uses test-id attribute"]
    return max(20, score), reasons


def _score_xpath(value: str) -> Tuple[int, List[str]]:
    reasons: List[str] = []
    score = 55
    depth = value.count("/")
    if depth >= 5:
        score -= 15
        reasons.append(f"deep xpath ({depth} segments)")
    if "text()" in value or "contains(" in value:
        score -= 15
        reasons.append("text-based xpath is locale-fragile")
    if "@id" in value:
        score += 15
        reasons.append("anchored on @id")
    if "@data" in value:
        score += 10
        reasons.append("anchored on data-* attribute")
    return max(15, min(score, 90)), reasons


def _score_text(value: str) -> Tuple[int, List[str]]:
    score = 35 if value else 0
    reasons = ["text-only locator (locale-fragile)"]
    return score, reasons


_DISPATCH = {
    "ID": _score_id,
    "id": _score_id,
    "NAME": lambda v: (70, []) if v else (0, ["empty name"]),
    "name": lambda v: (70, []) if v else (0, ["empty name"]),
    "CSS_SELECTOR": _score_css,
    "css selector": _score_css,
    "css": _score_css,
    "XPATH": _score_xpath,
    "xpath": _score_xpath,
    "TAG_NAME": lambda v: (25, ["matches every element of that tag"]) if v else (0, []),
    "tag name": lambda v: (25, ["matches every element of that tag"]) if v else (0, []),
    "CLASS_NAME": lambda v: (45, ["class names tend to drift"]) if v else (0, []),
    "class name": lambda v: (45, ["class names tend to drift"]) if v else (0, []),
    "LINK_TEXT": _score_text,
    "link text": _score_text,
    "PARTIAL_LINK_TEXT": _score_text,
    "partial link text": _score_text,
    "data-testid": _score_test_id_attr,
}


def score_locator(strategy: str, value: str) -> LocatorScore:
    """
    對單一 locator 評分
    Score a single ``(strategy, value)`` pair.
    """
    if not isinstance(strategy, str) or not isinstance(value, str):
        raise LocatorStrengthError(
            f"locator must be (str, str), got ({type(strategy).__name__}, {type(value).__name__})"
        )
    handler = _DISPATCH.get(strategy)
    if handler is None:
        raise LocatorStrengthError(f"unsupported locator strategy: {strategy!r}")
    score, reasons = handler(value)
    return LocatorScore(strategy=strategy, value=value, score=score, reasons=reasons)


def score_action_locators(actions: Iterable[Any]) -> List[Dict[str, Any]]:
    """
    從 action JSON 中抽取 ``{test_object_name, object_type}`` 評分
    Walk an action list and score every locator definition encountered.
    """
    findings: List[Dict[str, Any]] = []
    for index, action in enumerate(actions):
        if not isinstance(action, list) or not action:
            continue
        kwargs = _extract_kwargs(action)
        strategy = kwargs.get("object_type") or kwargs.get("strategy")
        value = kwargs.get("test_object_name") or kwargs.get("value")
        if strategy is None or value is None:
            continue
        try:
            score = score_locator(str(strategy), str(value))
        except LocatorStrengthError as error:
            findings.append({"index": index, "error": str(error)})
            continue
        findings.append({
            "index": index,
            "strategy": score.strategy,
            "value": score.value,
            "score": score.score,
            "reasons": score.reasons,
        })
    return findings


def _extract_kwargs(action: List[Any]) -> Dict[str, Any]:
    if len(action) >= 3 and isinstance(action[2], dict):
        return action[2]
    if len(action) >= 2 and isinstance(action[1], dict):
        return action[1]
    return {}


def weakest(findings: Iterable[Dict[str, Any]], threshold: int = 50) -> List[Dict[str, Any]]:
    """Return entries scoring at or below ``threshold``."""
    return [f for f in findings if isinstance(f.get("score"), int) and f["score"] <= threshold]


def assert_strength(findings: Iterable[Dict[str, Any]], minimum: int = 50,
                    raise_on_fail: bool = True) -> Optional[List[Dict[str, Any]]]:
    """Raise (or return) entries below ``minimum``."""
    bad = weakest(findings, threshold=minimum - 1)
    if bad and raise_on_fail:
        raise LocatorStrengthError(f"{len(bad)} locator(s) below {minimum}: {bad[:3]}")
    return bad
