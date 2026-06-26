"""
從 action JSON 自動標記 smoke / regression / perf / security / a11y / data。
Tagging tests by hand goes out of date fast. This module reads the
action list and picks tags based on what the test actually *does*:

* navigate + click + assert title → smoke
* WR_perf_* / lighthouse / loaf calls → perf
* login flow + payment → security
* axe / a11y_* / screen_reader_runner → a11y
* big data-driven loop → data

Heuristic is deliberately conservative; teams override via
``rules=[...custom_rules]``.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Sequence, Set, Union

from je_web_runner.utils.exception.exceptions import WebRunnerException


class TestCategorizerError(WebRunnerException):
    """Raised on malformed action JSON or invalid rules."""

    __test__ = False  # domain exception, not a pytest test class


# ---------- rule model -------------------------------------------------

@dataclass(frozen=True)
class Rule:
    """One categorisation rule."""

    tag: str
    matcher: Callable[[List[Dict[str, Any]]], bool]


def _has_any(action_name_pattern: str) -> Callable[[List[Dict[str, Any]]], bool]:
    regex = re.compile(action_name_pattern)
    def _check(actions: List[Dict[str, Any]]) -> bool:
        for action in actions:
            if not isinstance(action, dict) or len(action) != 1:
                continue
            name = next(iter(action.keys()))
            if regex.search(name):
                return True
        return False
    return _check


def _action_count_at_least(n: int) -> Callable[[List[Dict[str, Any]]], bool]:
    def _check(actions: List[Dict[str, Any]]) -> bool:
        return len(actions) >= n
    return _check


def _and(*matchers: Callable[[List[Dict[str, Any]]], bool]) -> Callable[[List[Dict[str, Any]]], bool]:
    def _check(actions: List[Dict[str, Any]]) -> bool:
        return all(m(actions) for m in matchers)
    return _check


DEFAULT_RULES: Sequence[Rule] = (
    # Smoke = "fast happy-path" — short test that navigates + asserts.
    Rule(tag="smoke", matcher=_and(
        _has_any(r"^WR_to_url$"),
        _has_any(r"^WR_assert_"),
        lambda actions: len(actions) <= 8,
    )),
    Rule(tag="regression", matcher=_and(
        _has_any(r"^WR_to_url$"),
        _has_any(r"^WR_assert_"),
        lambda actions: len(actions) > 8,
    )),
    Rule(tag="perf", matcher=_has_any(
        r"^WR_(?:perf_|lighthouse_|loaf_|inp_|cls_)",
    )),
    Rule(tag="a11y", matcher=_has_any(
        r"^WR_(?:axe_|a11y_|screen_reader_)",
    )),
    Rule(tag="security", matcher=_has_any(
        r"^WR_(?:csrf_|csp_|sri_|xss_|auth_|sanitize_)",
    )),
    Rule(tag="payment", matcher=_has_any(
        r"^WR_(?:stripe_|braintree_|paypal_|payment_)",
    )),
    Rule(tag="data_driven", matcher=_and(
        _action_count_at_least(40),
        _has_any(r"^WR_input_to_element$|^WR_assert_"),
    )),
    Rule(tag="visual", matcher=_has_any(
        r"^WR_(?:snapshot_|visual_|ocr_)",
    )),
    Rule(tag="api", matcher=_has_any(
        r"^WR_(?:http_|api_|graphql_|grpc_|sse_|ws_|webtransport_)",
    )),
)


# ---------- categorisation ---------------------------------------------

@dataclass
class CategoryAssignment:
    """Tag assignment for one test."""

    test_id: str
    tags: List[str] = field(default_factory=list)
    action_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def categorize_actions(
    actions: List[Dict[str, Any]],
    *,
    rules: Sequence[Rule] = DEFAULT_RULES,
) -> List[str]:
    """Return sorted list of tags that fire for ``actions``."""
    if not isinstance(actions, list):
        raise TestCategorizerError(
            f"actions must be a list, got {type(actions).__name__}"
        )
    for rule in rules:
        if not isinstance(rule, Rule):
            raise TestCategorizerError(
                f"rules entry must be Rule, got {type(rule).__name__}"
            )
    tags: Set[str] = set()
    for rule in rules:
        try:
            if rule.matcher(actions):
                tags.add(rule.tag)
        except Exception as error:
            raise TestCategorizerError(
                f"matcher for tag {rule.tag!r} raised: {error!r}"
            ) from error
    return sorted(tags)


def categorize_file(
    path: Union[str, Path],
    *,
    rules: Sequence[Rule] = DEFAULT_RULES,
) -> CategoryAssignment:
    """Load JSON file, run rules, return :class:`CategoryAssignment`."""
    p = Path(path)
    if not p.exists():
        raise TestCategorizerError(f"file not found: {p}")
    try:
        actions = json.loads(p.read_text(encoding="utf-8"))
    except ValueError as error:
        raise TestCategorizerError(f"file not JSON: {error}") from error
    if not isinstance(actions, list):
        raise TestCategorizerError(f"{p} must contain a JSON list")
    tags = categorize_actions(actions, rules=rules)
    return CategoryAssignment(
        test_id=str(p), tags=tags, action_count=len(actions),
    )


def categorize_dir(
    directory: Union[str, Path],
    *,
    rules: Sequence[Rule] = DEFAULT_RULES,
) -> List[CategoryAssignment]:
    """Categorize every ``*.json`` in a directory (non-recursive)."""
    d = Path(directory)
    if not d.is_dir():
        raise TestCategorizerError(f"not a directory: {d}")
    return [categorize_file(child, rules=rules)
            for child in sorted(d.glob("*.json"))]


# ---------- aggregation -----------------------------------------------

@dataclass
class TagDistribution:
    """Aggregated tag counts across a suite."""

    total_tests: int = 0
    untagged_tests: int = 0
    by_tag: Dict[str, int] = field(default_factory=dict)


def aggregate(assignments: Iterable[CategoryAssignment]) -> TagDistribution:
    dist = TagDistribution()
    for a in assignments:
        if not isinstance(a, CategoryAssignment):
            raise TestCategorizerError(
                f"aggregate expects CategoryAssignment, got {type(a).__name__}"
            )
        dist.total_tests += 1
        if not a.tags:
            dist.untagged_tests += 1
            continue
        for tag in a.tags:
            dist.by_tag[tag] = dist.by_tag.get(tag, 0) + 1
    return dist
