"""
Hallucination probe — a structured way to measure how often a model
invents facts on questions where you *know* the ground truth (or know
the answer should be "I don't know").

The harness takes:

* A list of ``Probe`` records each carrying a ``prompt``, an
  ``expected_substrings`` set (one of these must appear) and / or a
  ``forbidden_substrings`` set (none of these may appear).
* A ``Caller`` Protocol that runs one prompt and returns a string.

It returns a ``ProbeReport`` with per-probe pass/fail plus an aggregate
hallucination rate suitable for trend charts.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class HallucinationProbeError(WebRunnerException):
    """Raised on malformed probe input or budget violation."""


@dataclass
class Probe:
    name: str
    prompt: str
    expected_substrings: list[str] = field(default_factory=list)
    forbidden_substrings: list[str] = field(default_factory=list)
    expect_refusal: bool = False    # model should say "I don't know"

    def __post_init__(self) -> None:
        if not self.name:
            raise HallucinationProbeError("probe.name required")
        if not self.prompt:
            raise HallucinationProbeError("probe.prompt required")
        if (not self.expected_substrings and not self.forbidden_substrings
                and not self.expect_refusal):
            raise HallucinationProbeError(
                f"probe {self.name!r}: must declare expected, forbidden, "
                "or expect_refusal"
            )


_REFUSAL_PHRASES = (
    "i don't know", "i do not know", "i'm not sure", "i am not sure",
    "i cannot find", "no information",
)


def _looks_like_refusal(text: str) -> bool:
    lowered = (text or "").lower()
    return any(p in lowered for p in _REFUSAL_PHRASES)


@dataclass
class ProbeResult:
    name: str
    answer: str
    passed: bool
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProbeReport:
    results: list[ProbeResult] = field(default_factory=list)

    @property
    def hallucination_rate(self) -> float:
        if not self.results:
            return 0.0
        return sum(1 for r in self.results if not r.passed) / len(self.results)


Caller = Callable[[str], str]


def _evaluate(probe: Probe, answer: str) -> ProbeResult:
    if probe.expect_refusal:
        if _looks_like_refusal(answer):
            return ProbeResult(name=probe.name, answer=answer, passed=True)
        return ProbeResult(
            name=probe.name, answer=answer, passed=False,
            reason="expected a refusal but model gave a confident answer",
        )
    answer_l = (answer or "").lower()
    if probe.forbidden_substrings:
        for needle in probe.forbidden_substrings:
            if needle.lower() in answer_l:
                return ProbeResult(
                    name=probe.name, answer=answer, passed=False,
                    reason=f"contains forbidden substring {needle!r}",
                )
    if probe.expected_substrings:
        if not any(s.lower() in answer_l for s in probe.expected_substrings):
            return ProbeResult(
                name=probe.name, answer=answer, passed=False,
                reason=f"missing all expected substrings {probe.expected_substrings}",
            )
    return ProbeResult(name=probe.name, answer=answer, passed=True)


def run_probes(probes: Sequence[Probe], caller: Caller) -> ProbeReport:
    if not isinstance(probes, (list, tuple)) or not probes:
        raise HallucinationProbeError("probes must be a non-empty sequence")
    if not callable(caller):
        raise HallucinationProbeError("caller must be callable")
    report = ProbeReport()
    for probe in probes:
        try:
            answer = caller(probe.prompt)
        except Exception as error:
            report.results.append(ProbeResult(
                name=probe.name, answer="",
                passed=False, reason=f"caller raised {error!r}",
            ))
            continue
        if not isinstance(answer, str):
            report.results.append(ProbeResult(
                name=probe.name, answer="",
                passed=False, reason=f"caller returned {type(answer).__name__}",
            ))
            continue
        report.results.append(_evaluate(probe, answer))
    return report


def assert_hallucination_rate_under(
    report: ProbeReport, *, max_rate: float,
) -> None:
    if not 0 <= max_rate <= 1:
        raise HallucinationProbeError("max_rate must be in [0, 1]")
    rate = report.hallucination_rate
    if rate > max_rate:
        failed = [r.name for r in report.results if not r.passed]
        raise HallucinationProbeError(
            f"hallucination rate {rate:.2%} exceeds {max_rate:.2%}; "
            f"failing probes: {failed[:5]}{'…' if len(failed) > 5 else ''}"
        )
