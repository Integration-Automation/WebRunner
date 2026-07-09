"""
透過 CDP 降低硬體並發數 / 注入 memory-pressure 訊號,讓 suite 在低資源
條件下重跑,確認 UX 退化、不會崩潰、worker 收到 critical-memory 時釋
放快取。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

from je_web_runner.utils.exception.exceptions import WebRunnerException


_LOGGER = logging.getLogger(__name__)


class MemoryPressureError(WebRunnerException):
    """Raised on bad config or CDP integration failure."""


class PressureLevel(str, Enum):
    NOMINAL = "nominal"
    FAIR = "fair"
    SERIOUS = "serious"
    CRITICAL = "critical"


# ---------- emulation profile ------------------------------------------

@dataclass(frozen=True)
class EmulationProfile:
    """One memory + CPU emulation combo."""

    name: str
    hardware_concurrency: int = 2
    pressure_level: PressureLevel = PressureLevel.FAIR
    cpu_throttle_rate: float = 1.0  # 1.0 = normal, 4.0 = 4x slower
    js_heap_limit_bytes: int | None = None

    def __post_init__(self) -> None:
        if self.hardware_concurrency <= 0:
            raise MemoryPressureError("hardware_concurrency must be > 0")
        if self.cpu_throttle_rate < 1.0:
            raise MemoryPressureError("cpu_throttle_rate must be >= 1.0")
        if self.js_heap_limit_bytes is not None and self.js_heap_limit_bytes <= 0:
            raise MemoryPressureError("js_heap_limit_bytes must be > 0")


DEFAULT_PROFILES = (
    EmulationProfile(name="low_end_phone",
                     hardware_concurrency=2, cpu_throttle_rate=4.0,
                     pressure_level=PressureLevel.SERIOUS,
                     js_heap_limit_bytes=128 * 1024 * 1024),
    EmulationProfile(name="critical_pressure",
                     hardware_concurrency=4, cpu_throttle_rate=1.0,
                     pressure_level=PressureLevel.CRITICAL),
    EmulationProfile(name="single_core",
                     hardware_concurrency=1, cpu_throttle_rate=2.0,
                     pressure_level=PressureLevel.FAIR),
)


# ---------- CDP commands ------------------------------------------------

def cdp_payloads(profile: EmulationProfile) -> list[dict[str, Any]]:
    """
    Render the CDP commands a user's CDP-send callable should execute.
    Each entry is ``{"method": ..., "params": ...}``.
    """
    if not isinstance(profile, EmulationProfile):
        raise MemoryPressureError("profile must be EmulationProfile")
    commands: list[dict[str, Any]] = [
        {"method": "Emulation.setHardwareConcurrencyOverride",
         "params": {"hardwareConcurrency": profile.hardware_concurrency}},
        {"method": "Emulation.setCPUThrottlingRate",
         "params": {"rate": profile.cpu_throttle_rate}},
        # ``Memory.simulatePressureNotification`` is the Chrome experimental
        # endpoint; older builds use ``Memory.setPressureNotificationsSuppressed``.
        {"method": "Memory.simulatePressureNotification",
         "params": {"level": profile.pressure_level.value}},
    ]
    if profile.js_heap_limit_bytes is not None:
        commands.append({
            "method": "HeapProfiler.setSamplingHeapProfiler",
            "params": {"samplingInterval": profile.js_heap_limit_bytes},
        })
    return commands


# ---------- runner ------------------------------------------------------

@dataclass
class PressureRunOutcome:
    profile: str
    passed: bool
    duration_seconds: float = 0.0
    error: str | None = None


def run_under_profile(
    profile: EmulationProfile,
    cdp_send: Callable[[str, dict[str, Any]], Any],
    test_callable: Callable[[], None],
) -> PressureRunOutcome:
    """
    Apply ``profile`` via ``cdp_send``, run ``test_callable()``, restore
    defaults, return outcome.
    """
    if not callable(cdp_send):
        raise MemoryPressureError("cdp_send must be callable")
    if not callable(test_callable):
        raise MemoryPressureError("test_callable must be callable")
    import time
    try:
        for cmd in cdp_payloads(profile):
            cdp_send(cmd["method"], cmd["params"])
    except Exception as error:
        raise MemoryPressureError(f"CDP apply failed: {error!r}") from error
    started = time.monotonic()
    passed = True
    error_msg: str | None = None
    try:
        test_callable()
    except Exception as exc:
        passed = False
        error_msg = repr(exc)
    duration = round(time.monotonic() - started, 4)
    # Best-effort restore — don't mask the test failure if restore raises.
    try:
        cdp_send("Emulation.setHardwareConcurrencyOverride", {"hardwareConcurrency": 0})
        cdp_send("Emulation.setCPUThrottlingRate", {"rate": 1.0})
        cdp_send("Memory.simulatePressureNotification", {"level": "nominal"})
    except Exception as restore_err:
        # Don't mask the test result by re-raising here; CDP restore failure
        # is logged-only so a successful run isn't downgraded to error.
        _LOGGER.warning("CDP pressure restore failed: %r", restore_err)
    return PressureRunOutcome(
        profile=profile.name,
        passed=passed,
        duration_seconds=duration,
        error=error_msg,
    )


# ---------- assertion ---------------------------------------------------

def assert_passed_under_pressure(outcome: PressureRunOutcome) -> None:
    if not isinstance(outcome, PressureRunOutcome):
        raise MemoryPressureError("expects PressureRunOutcome")
    if not outcome.passed:
        raise MemoryPressureError(
            f"test failed under pressure profile {outcome.profile!r}: {outcome.error}"
        )
