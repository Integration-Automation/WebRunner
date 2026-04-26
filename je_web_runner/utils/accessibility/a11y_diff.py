"""
A11y diff：比較兩次 axe-core 跑完的結果，分出新增 / 修好 / 仍存在三組。
Compare two axe-core ``violations`` arrays and bucket each finding into
``added`` (regressed), ``resolved`` (fixed), or ``persisting`` (carry-
over). Identity is keyed on ``(rule_id, target)`` so the same rule on a
different element counts as a separate finding.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from je_web_runner.utils.exception.exceptions import WebRunnerException


class A11yDiffError(WebRunnerException):
    """Raised when input shape is invalid."""


@dataclass
class _Finding:
    rule_id: str
    target: str
    impact: Optional[str] = None
    summary: Optional[str] = None


@dataclass
class A11yDiff:
    added: List[Dict[str, Any]] = field(default_factory=list)
    resolved: List[Dict[str, Any]] = field(default_factory=list)
    persisting: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def regressed(self) -> bool:
        return bool(self.added)

    @property
    def total_baseline(self) -> int:
        return len(self.resolved) + len(self.persisting)

    @property
    def total_current(self) -> int:
        return len(self.added) + len(self.persisting)


def _flatten(violations: Iterable[Any]) -> List[_Finding]:
    findings: List[_Finding] = []
    for entry in violations:
        if not isinstance(entry, dict):
            raise A11yDiffError("violations entries must be objects")
        rule_id = str(entry.get("id") or entry.get("rule") or "")
        nodes = entry.get("nodes") or [{"target": entry.get("target")}]
        impact = entry.get("impact")
        summary = entry.get("description") or entry.get("help")
        for node in nodes:
            target = _node_target(node)
            findings.append(_Finding(
                rule_id=rule_id,
                target=target,
                impact=impact,
                summary=summary,
            ))
    return findings


def _node_target(node: Any) -> str:
    if isinstance(node, dict):
        target = node.get("target")
        if isinstance(target, list) and target:
            return ">".join(str(part) for part in target)
        if isinstance(target, str):
            return target
    if isinstance(node, str):
        return node
    return ""


def _to_dict(finding: _Finding) -> Dict[str, Any]:
    return {
        "rule_id": finding.rule_id,
        "target": finding.target,
        "impact": finding.impact,
        "summary": finding.summary,
    }


def diff_violations(
    baseline: Sequence[Any],
    current: Sequence[Any],
) -> A11yDiff:
    """Diff two axe-core ``violations`` arrays."""
    baseline_findings = _flatten(baseline)
    current_findings = _flatten(current)

    def keyed(items: Iterable[_Finding]) -> Dict[Tuple[str, str], _Finding]:
        return {(f.rule_id, f.target): f for f in items}

    baseline_keyed = keyed(baseline_findings)
    current_keyed = keyed(current_findings)
    added_keys = current_keyed.keys() - baseline_keyed.keys()
    resolved_keys = baseline_keyed.keys() - current_keyed.keys()
    persisting_keys = baseline_keyed.keys() & current_keyed.keys()
    diff = A11yDiff()
    for key in sorted(added_keys):
        diff.added.append(_to_dict(current_keyed[key]))
    for key in sorted(resolved_keys):
        diff.resolved.append(_to_dict(baseline_keyed[key]))
    for key in sorted(persisting_keys):
        diff.persisting.append(_to_dict(current_keyed[key]))
    return diff


def assert_no_regressions(diff: A11yDiff,
                          allow_rules: Optional[Sequence[str]] = None) -> None:
    """Raise if ``diff.added`` is non-empty (after applying ``allow_rules``)."""
    allow = set(allow_rules or [])
    bad = [a for a in diff.added if a.get("rule_id") not in allow]
    if bad:
        sample = [
            {"rule_id": a["rule_id"], "target": a["target"], "impact": a.get("impact")}
            for a in bad[:5]
        ]
        raise A11yDiffError(
            f"{len(bad)} new accessibility violation(s): {sample}"
        )
