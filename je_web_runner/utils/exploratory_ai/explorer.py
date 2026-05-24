"""
代理式探索測試員:LLM 主動決定下一步點哪、輸入甚麼,過程中蒐集 bug 報告線索。
The browser-driving and LLM-asking layers are pluggable so the core loop
stays unit-testable:

* :class:`PageObserver` — duck-typed protocol the explorer asks for the
  current page's URL / title / actionable interactive elements / console
  errors. A real implementation wraps Selenium or Playwright.
* :class:`ActionPlanner` — duck-typed protocol the explorer asks for the
  next :class:`PlannedAction` given the observation list. The default
  :class:`RandomPlanner` is deterministic with a seed and useful as a
  fuzz-style fallback when no LLM is configured.
* :class:`Explorer` — the loop. Runs N steps, gathers
  :class:`BugSignal`s from observed console errors / 4xx-5xx network
  hits, and returns a :class:`ExplorationReport`.
"""
from __future__ import annotations

import random
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Protocol, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class ExploratoryAiError(WebRunnerException):
    """Raised on observer/planner failures or invalid configuration."""


class ActionKind(str, Enum):
    """What :class:`PlannedAction` instructs the runner to do."""

    CLICK = "click"
    TYPE = "type"
    NAVIGATE = "navigate"
    SCROLL = "scroll"
    DONE = "done"


# ---------- data models -------------------------------------------------

@dataclass
class InteractiveElement:
    """A clickable / typeable element the observer surfaced."""

    selector: str
    tag: str
    text: str = ""
    role: Optional[str] = None
    is_visible: bool = True
    is_enabled: bool = True

    def __post_init__(self) -> None:
        if not self.selector or not isinstance(self.selector, str):
            raise ExploratoryAiError("InteractiveElement.selector must be non-empty string")
        if not self.tag or not isinstance(self.tag, str):
            raise ExploratoryAiError("InteractiveElement.tag must be non-empty string")


@dataclass
class PageObservation:
    """A snapshot of the page state passed to the planner."""

    url: str
    title: str
    elements: List[InteractiveElement] = field(default_factory=list)
    console_errors: List[str] = field(default_factory=list)
    network_errors: List[Dict[str, Any]] = field(default_factory=list)
    step: int = 0

    def actionable(self) -> List[InteractiveElement]:
        return [e for e in self.elements if e.is_visible and e.is_enabled]


@dataclass
class PlannedAction:
    """The next step the explorer wants the runner to perform."""

    kind: ActionKind
    selector: Optional[str] = None
    value: Optional[str] = None
    rationale: str = ""

    def __post_init__(self) -> None:
        if self.kind in (ActionKind.CLICK,) and not self.selector:
            raise ExploratoryAiError("click action requires selector")
        if self.kind == ActionKind.TYPE and (not self.selector or self.value is None):
            raise ExploratoryAiError("type action requires selector and value")
        if self.kind == ActionKind.NAVIGATE and not self.value:
            raise ExploratoryAiError("navigate action requires value (url)")


@dataclass
class BugSignal:
    """Something that looks broken; raised to the report."""

    step: int
    url: str
    kind: str  # 'console_error' | 'network_error' | 'planner_stuck' | ...
    detail: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExplorationReport:
    """Roll-up returned by :func:`Explorer.run`."""

    steps_taken: int
    pages_visited: List[str] = field(default_factory=list)
    bugs: List[BugSignal] = field(default_factory=list)
    actions: List[PlannedAction] = field(default_factory=list)
    stopped_reason: str = ""

    def has_bugs(self) -> bool:
        return bool(self.bugs)


# ---------- protocols ---------------------------------------------------

class PageObserver(Protocol):
    """Implementations wrap a browser driver to produce observations."""

    def observe(self, step: int) -> PageObservation: ...


class ActionPlanner(Protocol):
    """Decides the next action. Stateful planners may carry their own memory."""

    def plan(self, observation: PageObservation) -> PlannedAction: ...


# ---------- planners ----------------------------------------------------

class RandomPlanner:
    """
    Deterministic fuzz planner. Picks a random visible element to click,
    or types a random short string into the first input it finds. Useful
    on its own (no LLM needed) and as the fallback when an LLM planner
    fails.
    """

    def __init__(
        self,
        *,
        seed: Optional[int] = None,
        sample_strings: Sequence[str] = ("test", "1234", "x"),
        type_bias: float = 0.3,
    ) -> None:
        if not 0.0 <= type_bias <= 1.0:
            raise ExploratoryAiError("type_bias must be in [0, 1]")
        self._rng = random.Random(seed)
        self._samples = list(sample_strings) or ["x"]
        self._type_bias = type_bias

    def plan(self, observation: PageObservation) -> PlannedAction:
        actionable = observation.actionable()
        if not actionable:
            return PlannedAction(
                kind=ActionKind.DONE,
                rationale="no actionable elements on page",
            )
        inputs = [e for e in actionable if e.tag.lower() in {"input", "textarea"}]
        if inputs and self._rng.random() < self._type_bias:
            target = self._rng.choice(inputs)
            return PlannedAction(
                kind=ActionKind.TYPE,
                selector=target.selector,
                value=self._rng.choice(self._samples),
                rationale="random fuzz: fill an input",
            )
        target = self._rng.choice(actionable)
        return PlannedAction(
            kind=ActionKind.CLICK,
            selector=target.selector,
            rationale="random fuzz: click a visible element",
        )


# ---------- the loop ----------------------------------------------------

ActionExecutor = Callable[[PlannedAction], None]
"""Callable that performs the action against the real browser."""


@dataclass
class Explorer:
    """The exploratory loop. Hold one per session."""

    observer: PageObserver
    planner: ActionPlanner
    executor: ActionExecutor
    max_steps: int = 25
    max_repeat_loops: int = 3
    stop_on_bugs: int = 0  # 0 = never stop early

    def __post_init__(self) -> None:
        if self.max_steps <= 0:
            raise ExploratoryAiError("max_steps must be > 0")
        if self.max_repeat_loops < 0:
            raise ExploratoryAiError("max_repeat_loops must be >= 0")
        if self.stop_on_bugs < 0:
            raise ExploratoryAiError("stop_on_bugs must be >= 0")

    def run(self) -> ExplorationReport:
        report = ExplorationReport(steps_taken=0)
        repeat_counter: Dict[str, int] = {}
        for step in range(self.max_steps):
            observation = self._safe_observe(step)
            if observation.url and (
                not report.pages_visited or report.pages_visited[-1] != observation.url
            ):
                report.pages_visited.append(observation.url)
            self._collect_bug_signals(observation, report)
            if self.stop_on_bugs and len(report.bugs) >= self.stop_on_bugs:
                report.stopped_reason = (
                    f"hit stop_on_bugs={self.stop_on_bugs} ({len(report.bugs)} signals)"
                )
                break
            action = self._safe_plan(observation, report, repeat_counter)
            if action is None:
                report.stopped_reason = "planner repeatedly proposed same action; stopping"
                break
            if action.kind == ActionKind.DONE:
                report.stopped_reason = action.rationale or "planner said done"
                break
            report.actions.append(action)
            try:
                self.executor(action)
            except Exception as error:
                report.bugs.append(BugSignal(
                    step=step,
                    url=observation.url,
                    kind="action_error",
                    detail=f"{action.kind.value} failed: {error!r}",
                ))
            report.steps_taken = step + 1
        else:
            report.stopped_reason = f"reached max_steps={self.max_steps}"
        return report

    def _safe_observe(self, step: int) -> PageObservation:
        try:
            obs = self.observer.observe(step)
        except Exception as error:
            raise ExploratoryAiError(
                f"observer.observe failed at step {step}: {error!r}"
            ) from error
        if not isinstance(obs, PageObservation):
            raise ExploratoryAiError(
                f"observer.observe returned {type(obs).__name__}, want PageObservation"
            )
        return obs

    def _safe_plan(
        self,
        observation: PageObservation,
        report: ExplorationReport,
        repeat_counter: Dict[str, int],
    ) -> Optional[PlannedAction]:
        try:
            action = self.planner.plan(observation)
        except Exception as error:
            web_runner_logger.warning(f"planner failed; stopping: {error!r}")
            report.bugs.append(BugSignal(
                step=observation.step,
                url=observation.url,
                kind="planner_error",
                detail=repr(error),
            ))
            return None
        if not isinstance(action, PlannedAction):
            raise ExploratoryAiError(
                f"planner returned {type(action).__name__}, want PlannedAction"
            )
        key = f"{action.kind.value}:{action.selector or ''}:{action.value or ''}"
        repeat_counter[key] = repeat_counter.get(key, 0) + 1
        if repeat_counter[key] > self.max_repeat_loops:
            report.bugs.append(BugSignal(
                step=observation.step,
                url=observation.url,
                kind="planner_stuck",
                detail=f"action {key!r} chosen {repeat_counter[key]} times in a row",
            ))
            return None
        return action

    def _collect_bug_signals(
        self,
        observation: PageObservation,
        report: ExplorationReport,
    ) -> None:
        for message in observation.console_errors:
            report.bugs.append(BugSignal(
                step=observation.step,
                url=observation.url,
                kind="console_error",
                detail=message,
            ))
        for record in observation.network_errors:
            status = record.get("status") if isinstance(record, dict) else None
            url = record.get("url", "") if isinstance(record, dict) else ""
            report.bugs.append(BugSignal(
                step=observation.step,
                url=observation.url,
                kind="network_error",
                detail=f"{status} {url}",
            ))
