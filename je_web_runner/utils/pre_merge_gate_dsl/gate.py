"""
Declarative pre-merge gate DSL.

Lets the team express PR-merge requirements without scattering ad-hoc
``if`` rules across CI pipelines. Each ``Rule`` is one ``when`` /
``require`` pair:

    rules:
      - when:   "changed.has_path('src/payments/**')"
        require: ["pr_title_has_jira", "two_reviewers", "no_flake_regression"]
      - when:   "changed.is_docs_only"
        require: ["one_reviewer"]

The Python side parses a YAML / JSON / dict structure into ``Rule``
objects and evaluates them against a ``PrFacts`` snapshot.
"""
from __future__ import annotations

import fnmatch
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Iterable

from je_web_runner.utils.exception.exceptions import WebRunnerException


class PreMergeGateDslError(WebRunnerException):
    """Raised on malformed rules or input facts."""


@dataclass
class PrFacts:
    title: str = ""
    files_changed: list[str] = field(default_factory=list)
    additions: int = 0
    deletions: int = 0
    review_approvals: int = 0
    failing_checks: list[str] = field(default_factory=list)
    flake_score_delta: float = 0
    labels: list[str] = field(default_factory=list)

    @property
    def is_docs_only(self) -> bool:
        return bool(self.files_changed) and all(
            f.endswith(".md") or f.startswith("docs/")
            for f in self.files_changed
        )

    def has_path(self, glob: str) -> bool:
        return any(fnmatch.fnmatch(f, glob) for f in self.files_changed)


@dataclass
class Rule:
    when: str
    require: list[str]

    def __post_init__(self) -> None:
        if not isinstance(self.when, str) or not self.when:
            raise PreMergeGateDslError("rule.when must be non-empty string")
        if not isinstance(self.require, list) or not self.require:
            raise PreMergeGateDslError("rule.require must be non-empty list")


_WHEN_RE = re.compile(
    r"facts\.(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
    r"(?:\((?P<arg>'[^']*'|\"[^\"]*\")\))?",
)


def _safe_eval_when(expr: str, facts: PrFacts) -> bool:
    """Resolve ``facts.<attr>`` or ``facts.<method>("literal")`` by direct
    attribute / call lookup — no Python ``eval`` involved."""
    if not isinstance(expr, str):
        raise PreMergeGateDslError("when expression must be string")
    match = _WHEN_RE.fullmatch(expr.strip())
    if not match:
        raise PreMergeGateDslError(
            f"unsupported expression {expr!r}; "
            "only 'facts.<attr>' or 'facts.<method>(\"glob\")' allowed"
        )
    name = match.group("name")
    if not hasattr(facts, name):
        raise PreMergeGateDslError(
            f"failed to evaluate {expr!r}: PrFacts has no {name!r}"
        )
    target = getattr(facts, name)
    arg = match.group("arg")
    try:
        if arg is None:
            result = target
        else:
            literal = arg[1:-1]
            if not callable(target):
                raise PreMergeGateDslError(
                    f"{name!r} is not callable but expression supplies an argument"
                )
            result = target(literal)
    except Exception as error:
        raise PreMergeGateDslError(
            f"failed to evaluate {expr!r}: {error!r}"
        ) from error
    if not isinstance(result, bool):
        raise PreMergeGateDslError(
            f"when expression must yield bool, got {type(result).__name__}"
        )
    return result


# requirement name -> predicate (facts -> bool, "" or "reason string")
Predicate = Callable[[PrFacts], str | None]


def _pr_title_has_jira(facts: PrFacts) -> str | None:
    if re.search(r"\b[A-Z]{2,}-\d+\b", facts.title):
        return None
    return "PR title missing JIRA key (e.g. ABC-123)"


def _two_reviewers(facts: PrFacts) -> str | None:
    if facts.review_approvals >= 2:
        return None
    return f"need 2 reviewers, have {facts.review_approvals}"


def _one_reviewer(facts: PrFacts) -> str | None:
    if facts.review_approvals >= 1:
        return None
    return "need at least 1 reviewer"


def _no_failing_checks(facts: PrFacts) -> str | None:
    if not facts.failing_checks:
        return None
    return f"failing checks: {facts.failing_checks}"


def _no_flake_regression(facts: PrFacts) -> str | None:
    if facts.flake_score_delta <= 0.05:
        return None
    return f"flake score regressed by {facts.flake_score_delta:.2f}"


def _small_pr(facts: PrFacts) -> str | None:
    total = facts.additions + facts.deletions
    if total <= 400:
        return None
    return f"PR too large ({total} LOC > 400)"


BUILTIN_PREDICATES: dict[str, Predicate] = {
    "pr_title_has_jira": _pr_title_has_jira,
    "two_reviewers": _two_reviewers,
    "one_reviewer": _one_reviewer,
    "no_failing_checks": _no_failing_checks,
    "no_flake_regression": _no_flake_regression,
    "small_pr": _small_pr,
}


@dataclass
class GateResult:
    passed: bool
    failures: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_rules(raw: Any) -> list[Rule]:
    if not isinstance(raw, list):
        raise PreMergeGateDslError("rules must be a list of dicts")
    out: list[Rule] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise PreMergeGateDslError(f"rule #{i} must be a dict")
        out.append(Rule(when=item.get("when", ""),
                        require=list(item.get("require") or [])))
    return out


def evaluate(
    rules: Iterable[Rule],
    facts: PrFacts,
    predicates: dict[str, Predicate] | None = None,
) -> GateResult:
    if not isinstance(facts, PrFacts):
        raise PreMergeGateDslError("facts must be PrFacts")
    table = dict(BUILTIN_PREDICATES)
    if predicates:
        table.update(predicates)
    failures: list[str] = []
    for rule in rules:
        if not _safe_eval_when(rule.when, facts):
            continue
        for req in rule.require:
            pred = table.get(req)
            if pred is None:
                raise PreMergeGateDslError(f"unknown predicate {req!r}")
            problem = pred(facts)
            if problem:
                failures.append(f"[{req}] {problem}")
    return GateResult(passed=not failures, failures=failures)


def assert_gate_passes(result: GateResult) -> None:
    if not result.passed:
        raise PreMergeGateDslError(
            f"pre-merge gate failed: {result.failures}"
        )
