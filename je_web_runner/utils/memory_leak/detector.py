"""
重複跑同一動作後比對 ``performance.memory.usedJSHeapSize``，找疑似洩漏。
Memory leak detector. Drives a callable N times, sampling the JS heap
through ``performance.memory`` (Chromium-only) between rounds, then runs
linear regression to flag steady growth.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, List, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class MemoryLeakError(WebRunnerException):
    """Raised when the driver cannot report heap stats or growth exceeds budget."""


@dataclass
class MemorySample:
    """One heap-size sample after a round."""

    iteration: int
    used_heap_bytes: int


def sample_used_heap(driver: Any) -> int:
    """
    讀取 ``performance.memory.usedJSHeapSize``
    Selenium / Playwright friendly heap-size probe. Returns bytes.
    """
    expression = (
        "(window.performance && window.performance.memory) "
        "? window.performance.memory.usedJSHeapSize : -1"
    )
    if hasattr(driver, "execute_script"):
        value = driver.execute_script(f"return {expression};")
    elif hasattr(driver, "evaluate"):
        value = driver.evaluate(f"() => {expression}")
    else:
        raise MemoryLeakError("driver has neither execute_script nor evaluate")
    if not isinstance(value, (int, float)) or value < 0:
        raise MemoryLeakError("driver does not expose performance.memory")
    return int(value)


def _slope(samples: List[MemorySample]) -> float:
    n = len(samples)
    if n < 2:
        return 0.0
    sum_x = sum(s.iteration for s in samples)
    sum_y = sum(s.used_heap_bytes for s in samples)
    sum_xx = sum(s.iteration * s.iteration for s in samples)
    sum_xy = sum(s.iteration * s.used_heap_bytes for s in samples)
    denom = n * sum_xx - sum_x * sum_x
    if denom == 0:
        return 0.0
    return (n * sum_xy - sum_x * sum_y) / denom


def detect_growth(
    driver: Any,
    action: Callable[[], None],
    iterations: int = 5,
    warmup: int = 1,
    growth_bytes_per_iter_budget: Optional[int] = None,
    sampler: Optional[Callable[[Any], int]] = None,
) -> dict:
    """
    跑 ``action`` N 次，回傳每輪的 heap 樣本與線性斜率
    Run ``action`` ``iterations`` times (after ``warmup`` discarded rounds),
    sample the heap each round, and return the linear-fit slope so callers
    can decide whether memory is growing.

    :param growth_bytes_per_iter_budget: when set, raise if slope exceeds it.
    """
    if iterations < 2:
        raise MemoryLeakError("iterations must be >= 2 for trend detection")
    used_sampler = sampler or sample_used_heap
    for _ in range(max(0, warmup)):
        action()
        used_sampler(driver)  # discard
    samples: List[MemorySample] = []
    for index in range(iterations):
        action()
        size = used_sampler(driver)
        samples.append(MemorySample(iteration=index, used_heap_bytes=size))
        web_runner_logger.info(
            f"memory_leak iter={index} used_heap={size}"
        )
    slope = _slope(samples)
    summary = {
        "samples": [{"iteration": s.iteration, "used_heap_bytes": s.used_heap_bytes}
                    for s in samples],
        "slope_bytes_per_iter": slope,
        "delta_bytes": samples[-1].used_heap_bytes - samples[0].used_heap_bytes,
    }
    if (growth_bytes_per_iter_budget is not None
            and slope > growth_bytes_per_iter_budget):
        raise MemoryLeakError(
            f"heap grew {slope:.1f} B/iter, budget {growth_bytes_per_iter_budget}"
        )
    return summary
