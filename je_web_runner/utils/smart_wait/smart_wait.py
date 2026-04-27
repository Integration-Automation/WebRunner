"""
比 ``time.sleep`` 聰明的等待：監看 fetch idle、SPA 路由穩定。
Smart wait helpers that out-perform ``time.sleep`` for SPA flows. Hooks
``window.fetch`` to count in-flight requests and observes ``history``
mutations to detect route stabilisation.
"""
from __future__ import annotations

import time
from typing import Any, Callable, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class SmartWaitError(WebRunnerException):
    """Raised when a smart wait condition does not stabilise in time."""


_INSTALL_FETCH_HOOK = """
(() => {
  if (window.__wrFetchHook) { return; }
  window.__wrFetchInflight = 0;
  const original = window.fetch;
  window.fetch = function(...args) {
    window.__wrFetchInflight += 1;
    return original.apply(this, args).finally(() => {
      window.__wrFetchInflight = Math.max(0, window.__wrFetchInflight - 1);
    });
  };
  window.__wrFetchHook = true;
})();
"""


_INSTALL_HISTORY_HOOK = """
(() => {
  if (window.__wrHistoryHook) { return; }
  window.__wrLastRouteChange = Date.now();
  const wrap = (name) => {
    const orig = history[name];
    history[name] = function(...args) {
      window.__wrLastRouteChange = Date.now();
      return orig.apply(this, args);
    };
  };
  wrap("pushState");
  wrap("replaceState");
  window.addEventListener("popstate", () => {
    window.__wrLastRouteChange = Date.now();
  });
  window.__wrHistoryHook = true;
})();
"""


def install_hooks(driver: Any) -> None:
    """Inject the fetch + history hooks; idempotent."""
    from je_web_runner.utils.driver_dispatch import (
        DriverDispatchError, run_script,
    )
    try:
        run_script(driver, _INSTALL_FETCH_HOOK)
        run_script(driver, _INSTALL_HISTORY_HOOK)
    except DriverDispatchError as error:
        raise SmartWaitError(str(error)) from error


def _read_int(driver: Any, expression: str) -> int:
    from je_web_runner.utils.driver_dispatch import evaluate_expression
    return int(evaluate_expression(driver, expression))


def wait_until(
    predicate: Callable[[], bool],
    timeout: float = 10.0,
    poll: float = 0.1,
    sleep: Callable[[float], None] = time.sleep,
    description: str = "predicate",
) -> None:
    """Generic poll-until-true with timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if predicate():
                return
        except Exception as error:  # pylint: disable=broad-except
            web_runner_logger.debug(f"smart_wait predicate raised: {error!r}")
        sleep(poll)
    raise SmartWaitError(f"smart_wait timed out waiting for {description}")


def wait_for_fetch_idle(
    driver: Any,
    quiet_for: float = 0.5,
    timeout: float = 10.0,
    poll: float = 0.1,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """
    等到 ``window.fetch`` 在 ``quiet_for`` 秒內都沒有 in-flight 請求
    Wait until the fetch hook reports zero in-flight requests for at least
    ``quiet_for`` seconds.
    """
    install_hooks(driver)
    deadline = time.monotonic() + timeout
    quiet_started: Optional[float] = None
    while time.monotonic() < deadline:
        in_flight = _read_int(driver, "(window.__wrFetchInflight || 0)")
        now = time.monotonic()
        if in_flight == 0:
            if quiet_started is None:
                quiet_started = now
            elif now - quiet_started >= quiet_for:
                return
        else:
            quiet_started = None
        sleep(poll)
    raise SmartWaitError("fetch never went idle within timeout")


def wait_for_spa_route_stable(
    driver: Any,
    quiet_for: float = 0.4,
    timeout: float = 10.0,
    poll: float = 0.1,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """
    等到 ``history.pushState`` / ``replaceState`` / ``popstate``
    Wait until no history mutation has fired for at least ``quiet_for``\\ s.
    """
    install_hooks(driver)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        last_change_ms = _read_int(driver, "(window.__wrLastRouteChange || 0)")
        now_ms = _read_int(driver, "Date.now()")
        if (now_ms - last_change_ms) / 1000.0 >= quiet_for:
            return
        sleep(poll)
    raise SmartWaitError("SPA route never stabilised within timeout")
