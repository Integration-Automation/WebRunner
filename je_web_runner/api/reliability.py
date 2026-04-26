"""Façade: retries / locator strength / smart wait / throttler / pool / supervisor."""
from je_web_runner.utils.adaptive_retry.policy import (
    AdaptiveRetryError,
    RetryDecision,
    RetryPolicy,
    run_with_retry,
)
from je_web_runner.utils.browser_pool.pool import (
    BrowserPool,
    BrowserPoolError,
    PooledSession,
)
from je_web_runner.utils.linter.locator_strength import (
    LocatorScore,
    LocatorStrengthError,
    assert_strength,
    score_action_locators,
    score_locator,
)
from je_web_runner.utils.process_supervisor.supervisor import (
    KNOWN_DRIVER_NAMES,
    OrphanFinding,
    ProcessSupervisor,
    ProcessSupervisorError,
    with_watchdog,
)
from je_web_runner.utils.smart_wait.smart_wait import (
    SmartWaitError,
    wait_for_fetch_idle,
    wait_for_spa_route_stable,
    wait_until,
)
from je_web_runner.utils.throttler.throttler import (
    FileSemaphore,
    ServiceThrottler,
    ThrottlerError,
    throttle,
)

__all__ = [
    "AdaptiveRetryError", "RetryDecision", "RetryPolicy", "run_with_retry",
    "BrowserPool", "BrowserPoolError", "PooledSession",
    "LocatorScore", "LocatorStrengthError",
    "assert_strength", "score_action_locators", "score_locator",
    "KNOWN_DRIVER_NAMES", "OrphanFinding",
    "ProcessSupervisor", "ProcessSupervisorError", "with_watchdog",
    "SmartWaitError",
    "wait_for_fetch_idle", "wait_for_spa_route_stable", "wait_until",
    "FileSemaphore", "ServiceThrottler", "ThrottlerError", "throttle",
]
