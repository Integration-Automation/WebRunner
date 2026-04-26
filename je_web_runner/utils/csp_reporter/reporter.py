"""
CSP 報告收集器：在頁面注入監聽 ``securitypolicyviolation`` 事件，回傳記錄。
Inject a listener that records browser-fired ``securitypolicyviolation``
events into ``window.__wrCspViolations``, then read them back from Python
for assertion or reporting.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable, List, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException


class CspReporterError(WebRunnerException):
    """Raised when the reporter cannot inject or read violations."""


_INSTALL_LISTENER = """
(() => {
  if (window.__wrCspListenerInstalled) { return; }
  window.__wrCspViolations = [];
  document.addEventListener("securitypolicyviolation", (event) => {
    try {
      window.__wrCspViolations.push({
        violatedDirective: event.violatedDirective,
        effectiveDirective: event.effectiveDirective,
        blockedURI: event.blockedURI,
        sourceFile: event.sourceFile,
        lineNumber: event.lineNumber,
        statusCode: event.statusCode,
        documentURI: event.documentURI,
        referrer: event.referrer,
        sample: event.sample,
      });
    } catch (e) {}
  });
  window.__wrCspListenerInstalled = true;
})();
"""


_READ_VIOLATIONS = "JSON.stringify(window.__wrCspViolations || [])"


@dataclass
class CspViolation:
    violated_directive: str
    blocked_uri: str
    source_file: Optional[str]
    line_number: Optional[int]
    sample: Optional[str]


class CspViolationCollector:
    """Inject + read CSP-violation listener for a Selenium driver / Playwright page."""

    def __init__(self) -> None:
        self._violations: List[CspViolation] = []

    def install(self, driver: Any) -> None:
        from je_web_runner.utils.driver_dispatch import (
            DriverDispatchError, run_script,
        )
        try:
            run_script(driver, _INSTALL_LISTENER)
        except DriverDispatchError as error:
            raise CspReporterError(str(error)) from error

    def collect(self, driver: Any) -> List[CspViolation]:
        from je_web_runner.utils.driver_dispatch import (
            DriverDispatchError, evaluate_expression,
        )
        try:
            payload = evaluate_expression(driver, _READ_VIOLATIONS)
        except DriverDispatchError as error:
            raise CspReporterError(str(error)) from error
        if not isinstance(payload, str):
            raise CspReporterError(f"unexpected payload type: {type(payload).__name__}")
        try:
            entries = json.loads(payload)
        except ValueError as error:
            raise CspReporterError(f"violations JSON invalid: {error}") from error
        self._violations = [
            CspViolation(
                violated_directive=str(entry.get("violatedDirective", "")),
                blocked_uri=str(entry.get("blockedURI", "")),
                source_file=entry.get("sourceFile"),
                line_number=entry.get("lineNumber"),
                sample=entry.get("sample"),
            )
            for entry in entries
            if isinstance(entry, dict)
        ]
        return list(self._violations)

    def violations(self) -> List[CspViolation]:
        return list(self._violations)

    def assert_none(self) -> None:
        if self._violations:
            sample = [
                {"directive": v.violated_directive, "blocked": v.blocked_uri}
                for v in self._violations[:3]
            ]
            raise CspReporterError(f"{len(self._violations)} CSP violations: {sample}")

    def assert_no_directive(self, directive: str) -> None:
        match = [v for v in self._violations if v.violated_directive == directive]
        if match:
            raise CspReporterError(f"{len(match)} violation(s) for {directive!r}")


def install_listener(driver: Any) -> None:
    CspViolationCollector().install(driver)


def collect_violations(driver: Any) -> List[CspViolation]:
    return CspViolationCollector().collect(driver)


def assert_no_violations(driver: Any, allow_directives: Optional[Iterable[str]] = None) -> None:
    collector = CspViolationCollector()
    violations = collector.collect(driver)
    allowed = set(allow_directives or [])
    bad = [v for v in violations if v.violated_directive not in allowed]
    if bad:
        sample = [
            {"directive": v.violated_directive, "blocked": v.blocked_uri}
            for v in bad[:3]
        ]
        raise CspReporterError(f"{len(bad)} CSP violation(s): {sample}")
