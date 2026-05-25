"""
N+1 query detector for GraphQL operations.

Given a server-side trace (Apollo's ``tracing`` extension, ``federated_trace``,
or any list of ``{operation_name, sql, ms}`` rows), this module flags two
classic GraphQL performance smells:

* **Per-row child query**: same SQL template fires N times for a single
  GraphQL field (missing DataLoader / batch).
* **Cartesian fan-out**: nested resolver multiplies a parent's row count
  by a child's row count (a sign that the resolver should JOIN, not loop).
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, Iterable, List, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class GraphqlNPlus1Error(WebRunnerException):
    """Raised on malformed trace input or detected regression."""


class Severity(str, Enum):
    WARN = "warn"
    ERROR = "error"


@dataclass
class QueryRow:
    """One backend query observed during a GraphQL request."""

    operation: str = ""
    sql: str = ""
    ms: float = 0.0
    parent_field: str = ""

    @property
    def sql_template(self) -> str:
        """Strip literals so semantically identical queries collapse."""
        t = re.sub(r"'\w*'", "?", self.sql)
        t = re.sub(r"\b\d+\b", "?", t)
        t = re.sub(r"\s+", " ", t).strip()
        return t


@dataclass
class Finding:
    severity: Severity
    rule: str
    field: str
    repetitions: int
    template: str
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {**asdict(self), "severity": self.severity.value}


def parse_rows(payload: Any) -> List[QueryRow]:
    if not isinstance(payload, list):
        raise GraphqlNPlus1Error("payload must be a list of dicts")
    out: List[QueryRow] = []
    for raw in payload:
        if not isinstance(raw, dict):
            continue
        out.append(QueryRow(
            operation=str(raw.get("operation") or ""),
            sql=str(raw.get("sql") or ""),
            ms=float(raw.get("ms") or 0),
            parent_field=str(raw.get("parent_field") or raw.get("field") or ""),
        ))
    return out


def detect(rows: Sequence[QueryRow], threshold: int = 5) -> List[Finding]:
    """Find SQL templates repeated >= ``threshold`` times under one field."""
    if threshold < 2:
        raise GraphqlNPlus1Error("threshold must be >= 2")
    per_field: Dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        per_field[row.parent_field][row.sql_template] += 1
    findings: List[Finding] = []
    for field_name, counter in per_field.items():
        for template, count in counter.items():
            if count >= threshold:
                severity = (Severity.ERROR if count >= threshold * 2
                            else Severity.WARN)
                findings.append(Finding(
                    severity=severity,
                    rule="n-plus-one",
                    field=field_name or "(root)",
                    repetitions=count,
                    template=template,
                    note=("Likely missing DataLoader batching for field "
                          f"{field_name or '(root)'}"),
                ))
    return findings


def detect_cartesian(rows: Sequence[QueryRow]) -> List[Finding]:
    """Flag fields whose total queries > parent_field's queries * 10."""
    per_field: Counter = Counter()
    for row in rows:
        per_field[row.parent_field] += 1
    findings: List[Finding] = []
    if not per_field:
        return findings
    parent_count = min(per_field.values())
    for field_name, count in per_field.items():
        if count > parent_count * 10:
            findings.append(Finding(
                severity=Severity.WARN, rule="cartesian-fanout",
                field=field_name or "(root)", repetitions=count,
                template="", note="Resolver appears to scale with parent×child.",
            ))
    return findings


def assert_no_n_plus_1(findings: Iterable[Finding]) -> None:
    bad = [f for f in findings if f.severity == Severity.ERROR]
    if bad:
        raise GraphqlNPlus1Error(
            f"N+1 detected: {[(f.field, f.repetitions) for f in bad]}"
        )


def report_markdown(findings: Iterable[Finding]) -> str:
    findings = list(findings)
    if not findings:
        return "## GraphQL N+1 audit\n_No N+1 patterns detected._"
    lines = ["## GraphQL N+1 audit"]
    for f in findings:
        marker = "❌" if f.severity == Severity.ERROR else "⚠️"
        lines.append(
            f"- {marker} `{f.field}` × {f.repetitions} — `{f.template[:60]}`"
        )
    return "\n".join(lines)
