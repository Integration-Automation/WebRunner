"""
追蹤 JS console errors / unhandled rejections,設立可調的「錯誤預算」。
A budget exists so non-critical noise doesn't fail every CI run, while
genuinely-spiked runs still trip. Three knobs:

* **Severity filter** — ignore ``log`` / ``info`` / ``debug`` by default;
  ``error`` and ``warning`` (configurable) count.
* **Pattern allowlist** — regex skiplist for known-third-party noise
  (e.g. ``/extensions/.*ResizeObserver/``).
* **Max count** — overall cap. ``allowed_warnings`` is a separate softer
  budget so a single error still fails.

Designed to be fed by anything that produces :class:`ConsoleMessage`s —
a CDP listener (``Runtime.consoleAPICalled`` / ``Runtime.exceptionThrown``),
``selenium.webdriver.remote.webdriver.WebDriver.get_log("browser")``,
Playwright ``page.on('console')``, etc.
"""
from __future__ import annotations

import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Pattern, Sequence, Union

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class ConsoleBudgetError(WebRunnerException):
    """Raised when the budget is exceeded or input is malformed."""


_KNOWN_SEVERITIES = ("debug", "info", "log", "warning", "error")


# ---------- model -------------------------------------------------------

@dataclass
class ConsoleMessage:
    """One console line. Severity is normalised to the strings above."""

    severity: str
    text: str
    url: Optional[str] = None
    line: Optional[int] = None
    timestamp: float = field(default_factory=time.time)
    source: Optional[str] = None  # 'console' or 'exception' or driver-specific

    def __post_init__(self) -> None:
        normalised = (self.severity or "").lower()
        if normalised == "warn":
            normalised = "warning"
        elif normalised == "severe":  # selenium's level for console.error
            normalised = "error"
        if normalised not in _KNOWN_SEVERITIES:
            normalised = "info"
        object.__setattr__(self, "severity", normalised)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BudgetReport:
    """Outcome of :func:`evaluate`."""

    passed: bool
    error_count: int
    warning_count: int
    ignored_count: int
    breaches: List[str] = field(default_factory=list)
    sampled: List[ConsoleMessage] = field(default_factory=list)

    def raise_if_failed(self) -> None:
        if not self.passed:
            joined = "; ".join(self.breaches) or "budget exceeded"
            raise ConsoleBudgetError(joined)


@dataclass
class ErrorBudget:
    """Per-suite knobs for what counts and how much is allowed."""

    max_errors: int = 0
    max_warnings: int = 5
    count_warnings: bool = True
    ignore_patterns: Sequence[Union[str, Pattern[str]]] = ()
    sample_size: int = 10

    def __post_init__(self) -> None:
        if self.max_errors < 0 or self.max_warnings < 0:
            raise ConsoleBudgetError("max_errors / max_warnings must be >= 0")
        if self.sample_size < 0:
            raise ConsoleBudgetError("sample_size must be >= 0")


# ---------- evaluator ---------------------------------------------------

def _compiled_patterns(
    patterns: Sequence[Union[str, Pattern[str]]],
) -> List[Pattern[str]]:
    compiled: List[Pattern[str]] = []
    for p in patterns:
        if hasattr(p, "search"):
            compiled.append(p)  # type: ignore[arg-type]
        else:
            try:
                compiled.append(re.compile(str(p)))
            except re.error as error:
                raise ConsoleBudgetError(f"bad ignore pattern {p!r}: {error}") from error
    return compiled


def _is_ignored(message: ConsoleMessage, patterns: List[Pattern[str]]) -> bool:
    if not patterns:
        return False
    haystack = f"{message.text}\n{message.url or ''}"
    return any(p.search(haystack) for p in patterns)


def evaluate(
    messages: Iterable[ConsoleMessage],
    budget: ErrorBudget,
) -> BudgetReport:
    """Score ``messages`` against ``budget`` and return a :class:`BudgetReport`."""
    if not isinstance(budget, ErrorBudget):
        raise ConsoleBudgetError("budget must be an ErrorBudget instance")
    patterns = _compiled_patterns(budget.ignore_patterns)
    errors: List[ConsoleMessage] = []
    warnings: List[ConsoleMessage] = []
    ignored = 0
    for msg in messages:
        if not isinstance(msg, ConsoleMessage):
            raise ConsoleBudgetError(
                f"evaluate expects ConsoleMessage, got {type(msg).__name__}"
            )
        if _is_ignored(msg, patterns):
            ignored += 1
            continue
        if msg.severity == "error":
            errors.append(msg)
        elif msg.severity == "warning" and budget.count_warnings:
            warnings.append(msg)
    breaches: List[str] = []
    if len(errors) > budget.max_errors:
        breaches.append(
            f"errors {len(errors)} > max_errors {budget.max_errors}"
        )
    if budget.count_warnings and len(warnings) > budget.max_warnings:
        breaches.append(
            f"warnings {len(warnings)} > max_warnings {budget.max_warnings}"
        )
    sampled = (errors + warnings)[: budget.sample_size]
    report = BudgetReport(
        passed=not breaches,
        error_count=len(errors),
        warning_count=len(warnings),
        ignored_count=ignored,
        breaches=breaches,
        sampled=sampled,
    )
    if breaches:
        web_runner_logger.warning(
            f"console budget breach: {breaches} (errors={len(errors)}, "
            f"warnings={len(warnings)}, ignored={ignored})"
        )
    return report


# ---------- adapters ----------------------------------------------------

def from_selenium_log(entries: Iterable[Dict[str, Any]]) -> List[ConsoleMessage]:
    """Convert Selenium ``driver.get_log('browser')`` entries to messages."""
    out: List[ConsoleMessage] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        out.append(ConsoleMessage(
            severity=str(entry.get("level") or "info"),
            text=str(entry.get("message") or ""),
            timestamp=float(entry.get("timestamp") or 0) / 1000.0 or time.time(),
            source="selenium-browser-log",
        ))
    return out


def from_cdp_console_events(events: Iterable[Dict[str, Any]]) -> List[ConsoleMessage]:
    """
    Convert CDP ``Runtime.consoleAPICalled`` payloads into messages.
    Each event dict is expected to have ``type`` and ``args`` like CDP returns.
    """
    out: List[ConsoleMessage] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        args = event.get("args") or []
        text_parts: List[str] = []
        for arg in args:
            if isinstance(arg, dict):
                value = arg.get("value")
                if value is not None:
                    text_parts.append(str(value))
                elif arg.get("description"):
                    text_parts.append(str(arg["description"]))
        out.append(ConsoleMessage(
            severity=str(event.get("type") or "log"),
            text=" ".join(text_parts).strip(),
            url=(event.get("stackTrace") or {}).get("url"),
            timestamp=float(event.get("timestamp") or 0) / 1000.0 or time.time(),
            source="cdp-console",
        ))
    return out


def from_cdp_exception_events(events: Iterable[Dict[str, Any]]) -> List[ConsoleMessage]:
    """Convert CDP ``Runtime.exceptionThrown`` payloads to error messages."""
    out: List[ConsoleMessage] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        details = event.get("exceptionDetails") or {}
        text = (details.get("exception") or {}).get("description") or details.get("text") or ""
        out.append(ConsoleMessage(
            severity="error",
            text=str(text),
            url=details.get("url"),
            line=details.get("lineNumber"),
            timestamp=float(event.get("timestamp") or 0) / 1000.0 or time.time(),
            source="cdp-exception",
        ))
    return out
