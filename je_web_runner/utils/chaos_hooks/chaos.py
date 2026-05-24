"""
在 action 流程中隨機注入混亂條件:網路斷線、CPU 節流、中途 reload。
Verifies the UX recovers, retries, or shows the right error UI — not just
that the happy path works on a perfect machine.

Three deliberately decoupled pieces:

* :class:`ChaosPlan` — pure scheduling. Given a list of action names and
  a seed, deterministically decides which step gets which fault. No
  browser dependency; fully unit-testable.
* :class:`ChaosFaultType` — enum of fault categories. Each maps to an
  injector callable provided by the user (so this module doesn't import
  Selenium/CDP/Playwright).
* :class:`ChaosRunner` — runs a plan against an executor by invoking the
  matching injector before the chosen step.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class ChaosHooksError(WebRunnerException):
    """Raised on bad plan parameters or missing injector for a chosen fault."""


class ChaosFaultType(str, Enum):
    """Categories of chaos a runner can inject."""

    NETWORK_OFFLINE = "network_offline"
    NETWORK_SLOW = "network_slow"
    CPU_THROTTLE = "cpu_throttle"
    MID_FLOW_RELOAD = "mid_flow_reload"
    TAB_BACKGROUND = "tab_background"


# ---------- planning ----------------------------------------------------

@dataclass(frozen=True)
class ChaosEvent:
    """One scheduled fault."""

    step_index: int
    step_name: str
    fault: ChaosFaultType


@dataclass
class ChaosPlan:
    """A reproducible (seeded) injection schedule."""

    events: List[ChaosEvent] = field(default_factory=list)
    seed: Optional[int] = None
    skipped: List[int] = field(default_factory=list)

    def faults_for_step(self, index: int) -> List[ChaosFaultType]:
        return [e.fault for e in self.events if e.step_index == index]

    def describe(self) -> str:
        if not self.events:
            return "no chaos planned"
        rows = [
            f"step {e.step_index} ({e.step_name}): {e.fault.value}"
            for e in self.events
        ]
        return "; ".join(rows)


def plan_chaos(
    step_names: Sequence[str],
    *,
    faults: Sequence[ChaosFaultType] = tuple(ChaosFaultType),
    fault_rate: float = 0.2,
    max_events: Optional[int] = None,
    skip_first: int = 1,
    skip_last: int = 0,
    seed: Optional[int] = None,
) -> ChaosPlan:
    """
    決定每個 step 是否注入 chaos,以及注入哪種類型。
    Each non-skipped step independently has ``fault_rate`` chance of
    getting a randomly-chosen fault from ``faults``. ``max_events`` caps
    the total. ``skip_first`` / ``skip_last`` keep setup / teardown safe.
    """
    if not 0.0 <= fault_rate <= 1.0:
        raise ChaosHooksError("fault_rate must be in [0, 1]")
    if not faults:
        raise ChaosHooksError("faults must be a non-empty sequence")
    if skip_first < 0 or skip_last < 0:
        raise ChaosHooksError("skip_first / skip_last must be >= 0")
    total = len(step_names)
    rng = random.Random(seed)  # nosec B311 — deterministic test scheduling, not crypto
    events: List[ChaosEvent] = []
    skipped: List[int] = []
    for index, name in enumerate(step_names):
        if index < skip_first or index >= total - skip_last:
            skipped.append(index)
            continue
        # S2245 ok: deterministic seeded scheduling for tests; not cryptographic.
        if rng.random() >= fault_rate:  # noqa: S2245
            continue
        fault = rng.choice(list(faults))  # noqa: S2245
        events.append(ChaosEvent(step_index=index, step_name=name, fault=fault))
        if max_events is not None and len(events) >= max_events:
            break
    return ChaosPlan(events=events, seed=seed, skipped=skipped)


# ---------- runner ------------------------------------------------------

Injector = Callable[[ChaosEvent], None]
"""Callable that performs the side effect for one event (offline, throttle, etc.)."""


@dataclass
class ChaosRunner:
    """Runs a :class:`ChaosPlan` by invoking the matching injector pre-step."""

    plan: ChaosPlan
    injectors: Dict[ChaosFaultType, Injector] = field(default_factory=dict)
    raise_on_missing: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.plan, ChaosPlan):
            raise ChaosHooksError("plan must be a ChaosPlan")
        missing = [
            event.fault for event in self.plan.events
            if event.fault not in self.injectors
        ]
        if missing and self.raise_on_missing:
            unique = sorted({m.value for m in missing})
            raise ChaosHooksError(
                f"no injector registered for fault types: {unique}"
            )

    def before_step(self, index: int, name: str) -> List[ChaosEvent]:
        """Fire every injector scheduled for ``index``; return events fired."""
        fired: List[ChaosEvent] = []
        for event in self.plan.events:
            if event.step_index != index:
                continue
            injector = self.injectors.get(event.fault)
            if injector is None:
                web_runner_logger.warning(
                    f"chaos: no injector for {event.fault.value} at step {index} ({name})"
                )
                continue
            try:
                injector(event)
            except Exception as error:
                raise ChaosHooksError(
                    f"injector {event.fault.value} raised at step {index}: {error!r}"
                ) from error
            fired.append(event)
            web_runner_logger.info(
                f"chaos: injected {event.fault.value} before step {index} ({name})"
            )
        return fired


# ---------- convenience -------------------------------------------------

def run_with_chaos(
    step_names: Sequence[str],
    step_fn: Callable[[int, str], None],
    *,
    plan: ChaosPlan,
    injectors: Dict[ChaosFaultType, Injector],
) -> List[ChaosEvent]:
    """
    Drive ``step_fn(index, name)`` for every step, firing scheduled
    injectors immediately before each step. Returns the events that fired.
    """
    runner = ChaosRunner(plan=plan, injectors=injectors)
    fired: List[ChaosEvent] = []
    for index, name in enumerate(step_names):
        fired.extend(runner.before_step(index, name))
        step_fn(index, name)
    return fired
