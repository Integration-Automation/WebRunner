"""
Persona matrix: 同一份 suite × N 種角色(admin / free / enterprise / guest)。
Most apps have feature gates by role. Re-running every action JSON file
under every persona catches "free user saw an admin-only button" or
"enterprise user can't see the feature they paid for".

Inputs:

* :class:`Persona` — name + auth-state hook + optional flag overrides
* :class:`PersonaRunner.run` — iterate (persona × action_file) and call
  the user's runner callable for each pair

Outputs:

* :class:`PersonaCaseResult` per pair, and a :class:`MatrixSummary`
  helping the reader see "all failures are on persona=guest" at a glance
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Protocol, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class PersonaRunnerError(WebRunnerException):
    """Raised on bad persona / action-file inputs."""


# ---------- persona model -----------------------------------------------

@dataclass
class Persona:
    """One identity under test."""

    name: str
    auth_state: Dict[str, Any] = field(default_factory=dict)
    flags: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.name or not isinstance(self.name, str):
            raise PersonaRunnerError("Persona.name must be non-empty string")


# ---------- result model ------------------------------------------------

@dataclass
class PersonaCaseResult:
    """Outcome of one (persona, action_file) pair."""

    persona: str
    action_file: str
    passed: bool
    duration_seconds: float = 0.0
    error: Optional[str] = None
    notes: List[str] = field(default_factory=list)


@dataclass
class MatrixSummary:
    """Roll-up across all pairs."""

    total: int
    passed: int
    failed: int
    by_persona: Dict[str, Dict[str, int]] = field(default_factory=dict)
    persona_only_failures: List[str] = field(default_factory=list)
    file_only_failures: List[str] = field(default_factory=list)


# ---------- runner protocol --------------------------------------------

class PersonaCaseRunner(Protocol):
    """Implementations execute one action file under one persona."""

    def __call__(self, persona: Persona, action_file: str) -> None: ...


# ---------- the runner --------------------------------------------------

@dataclass
class PersonaRunner:
    """Drive the persona × file matrix."""

    personas: Sequence[Persona]
    action_files: Sequence[str]
    case_runner: PersonaCaseRunner
    stop_on_first_failure: bool = False

    def __post_init__(self) -> None:
        if not self.personas:
            raise PersonaRunnerError("at least one persona is required")
        names = [p.name for p in self.personas]
        if len(set(names)) != len(names):
            raise PersonaRunnerError(f"duplicate persona names: {names}")
        if not self.action_files:
            raise PersonaRunnerError("at least one action file is required")
        if len(set(self.action_files)) != len(self.action_files):
            raise PersonaRunnerError("duplicate action_files in matrix")

    def run(self) -> List[PersonaCaseResult]:
        results: List[PersonaCaseResult] = []
        for persona in self.personas:
            for action_file in self.action_files:
                started = time.monotonic()
                error: Optional[str] = None
                try:
                    self.case_runner(persona, action_file)
                    passed = True
                except PersonaRunnerError:
                    raise
                except Exception as exc:
                    passed = False
                    error = repr(exc)
                    web_runner_logger.warning(
                        f"persona={persona.name!r} file={action_file!r} failed: {exc!r}"
                    )
                duration = round(time.monotonic() - started, 4)
                results.append(PersonaCaseResult(
                    persona=persona.name,
                    action_file=action_file,
                    passed=passed,
                    duration_seconds=duration,
                    error=error,
                ))
                if not passed and self.stop_on_first_failure:
                    return results
        return results


# ---------- summary -----------------------------------------------------

def summarise(results: Iterable[PersonaCaseResult]) -> MatrixSummary:
    """Build a :class:`MatrixSummary` from a result iterable."""
    total = 0
    passed_count = 0
    by_persona: Dict[str, Dict[str, int]] = {}
    failures_by_persona: Dict[str, List[str]] = {}
    failures_by_file: Dict[str, List[str]] = {}
    seen_personas: set = set()
    seen_files: set = set()
    for result in results:
        if not isinstance(result, PersonaCaseResult):
            raise PersonaRunnerError(
                f"summarise expects PersonaCaseResult, got {type(result).__name__}"
            )
        total += 1
        seen_personas.add(result.persona)
        seen_files.add(result.action_file)
        bucket = by_persona.setdefault(result.persona, {"passed": 0, "failed": 0})
        if result.passed:
            bucket["passed"] += 1
            passed_count += 1
        else:
            bucket["failed"] += 1
            failures_by_persona.setdefault(result.persona, []).append(result.action_file)
            failures_by_file.setdefault(result.action_file, []).append(result.persona)
    persona_only: List[str] = []
    for persona, failed_files in failures_by_persona.items():
        # A persona "only" fails if every other persona passes the same files
        if all(
            persona not in failures_by_file.get(file, [])
            or len(failures_by_file.get(file, [])) == 1
            for file in failed_files
        ):
            persona_only.append(persona)
    file_only: List[str] = []
    for file, failing_personas in failures_by_file.items():
        if len(set(failing_personas)) >= len(seen_personas):
            file_only.append(file)
    return MatrixSummary(
        total=total,
        passed=passed_count,
        failed=total - passed_count,
        by_persona=by_persona,
        persona_only_failures=sorted(persona_only),
        file_only_failures=sorted(file_only),
    )


# ---------- formatting --------------------------------------------------

def summary_markdown(summary: MatrixSummary) -> str:
    """Render a small markdown table for PR comments."""
    if summary.total == 0:
        return "_No persona matrix results._\n"
    lines = [
        f"### Persona matrix: {summary.passed}/{summary.total} passed",
        "",
        "| Persona | Passed | Failed |",
        "|---------|--------|--------|",
    ]
    for persona in sorted(summary.by_persona):
        bucket = summary.by_persona[persona]
        lines.append(f"| {persona} | {bucket['passed']} | {bucket['failed']} |")
    if summary.persona_only_failures:
        lines.append("")
        lines.append(
            "**Persona-specific regressions:** "
            + ", ".join(summary.persona_only_failures)
        )
    if summary.file_only_failures:
        lines.append("")
        lines.append(
            "**Files failing on every persona:** "
            + ", ".join(summary.file_only_failures)
        )
    return "\n".join(lines) + "\n"
