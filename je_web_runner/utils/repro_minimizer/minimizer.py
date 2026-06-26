"""
把失敗的 action list 縮到最小可重現 — delta-debugging (ddmin) 演算法。
Given a list of N actions that fails, ddmin finds the smallest
subsequence that *still* fails by partitioning + binary-style elimination.
For E2E tests this is enormously useful: a 60-action recorder dump
shrinks to 4 actions that reproduce the bug.

The runner callable is supplied by the caller (it knows how to execute
WR action JSON). It should return ``True`` when the test *passes* and
``False`` when it fails — minimizer is hunting for the failure-preserving
minimal subset.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class ReproMinimizerError(WebRunnerException):
    """Raised on bad inputs or runner failure."""


# ---------- result model -----------------------------------------------

@dataclass
class MinimizationResult:
    """Outcome returned by :func:`minimize`."""

    original_size: int
    minimized_actions: list[Any]
    minimized_size: int
    iterations: int = 0
    eval_count: int = 0
    duration_seconds: float = 0.0

    @property
    def reduction_pct(self) -> float:
        if self.original_size <= 0:
            return 0.0
        return (1.0 - self.minimized_size / self.original_size) * 100.0


# ---------- runner protocol --------------------------------------------

# Runner returns True if the (sub)sequence still *passes* the test
# (i.e. doesn't reproduce the failure), False if it still fails.
ActionRunner = Callable[[list[Any]], bool]


# ---------- ddmin -------------------------------------------------------

def minimize(  # NOSONAR S3776 — cohesive logic; planned refactor in follow-up
    actions: Sequence[Any],
    runner: ActionRunner,
    *,
    max_iterations: int = 200,
    verify_failing: bool = True,
) -> MinimizationResult:
    """
    Classic ddmin. Returns the smallest contiguous-or-not subsequence of
    ``actions`` that still causes ``runner`` to return ``False``.
    """
    if not isinstance(actions, (list, tuple)):
        raise ReproMinimizerError(
            f"actions must be list/tuple, got {type(actions).__name__}"
        )
    if not actions:
        raise ReproMinimizerError("actions must be non-empty")
    if not callable(runner):
        raise ReproMinimizerError("runner must be callable")
    if max_iterations <= 0:
        raise ReproMinimizerError("max_iterations must be > 0")

    counter = {"evals": 0}

    def _evaluate(subset: list[Any]) -> bool:
        counter["evals"] += 1
        try:
            return bool(runner(subset))
        except Exception as error:
            raise ReproMinimizerError(
                f"runner raised at size {len(subset)}: {error!r}"
            ) from error

    full = list(actions)
    if verify_failing and _evaluate(full):
        raise ReproMinimizerError(
            "runner says the original action list PASSES; nothing to minimize"
        )

    started = time.monotonic()
    current = full
    n = 2
    iterations = 0
    while len(current) >= 2 and iterations < max_iterations:
        iterations += 1
        chunk_size = max(1, len(current) // n)
        chunks = [current[i:i + chunk_size]
                  for i in range(0, len(current), chunk_size)]
        # Try removing complement of each chunk first (granularity = n).
        reduced = False
        for index, chunk in enumerate(chunks):
            complement = [
                a for j, c in enumerate(chunks) if j != index for a in c
            ]
            if not complement:
                continue
            if not _evaluate(complement):
                current = complement
                n = max(n - 1, 2)
                reduced = True
                break
        if not reduced:
            if n >= len(current):
                break
            n = min(n * 2, len(current))
    duration = round(time.monotonic() - started, 4)
    if iterations >= max_iterations:
        web_runner_logger.warning(
            f"repro_minimizer hit max_iterations={max_iterations}; "
            "result may not be locally minimal"
        )
    return MinimizationResult(
        original_size=len(full),
        minimized_actions=current,
        minimized_size=len(current),
        iterations=iterations,
        eval_count=counter["evals"],
        duration_seconds=duration,
    )


# ---------- helpers ----------------------------------------------------

def assert_minimized(
    result: MinimizationResult,
    *,
    max_remaining: int,
) -> None:
    """Assert ``minimized_size <= max_remaining``."""
    if not isinstance(result, MinimizationResult):
        raise ReproMinimizerError("assert_minimized expects MinimizationResult")
    if max_remaining < 0:
        raise ReproMinimizerError("max_remaining must be >= 0")
    if result.minimized_size > max_remaining:
        raise ReproMinimizerError(
            f"minimized to {result.minimized_size} actions, "
            f"wanted <= {max_remaining}"
        )


def report_markdown(result: MinimizationResult) -> str:
    """Render a small markdown summary."""
    if not isinstance(result, MinimizationResult):
        raise ReproMinimizerError("report_markdown expects MinimizationResult")
    return (
        f"### Minimal repro: {result.minimized_size} / {result.original_size} "
        f"actions ({result.reduction_pct:.0f}% reduction)\n\n"
        f"- iterations: {result.iterations}\n"
        f"- runner evaluations: {result.eval_count}\n"
        f"- duration: {result.duration_seconds:.2f}s\n"
    )
