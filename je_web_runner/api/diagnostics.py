"""Facade: Run diagnostics: trace propagation, backend log correlation, console error budgets."""
from je_web_runner.utils.backend_log_correlator.correlator import (
    BackendLogCorrelatorError, CorrelatedLog, parse_traceparent as backend_log_correlator_parse_traceparent,
    validate_trace_id, fetch_file_log, fetch_loki, fetch_elasticsearch, correlate, attach_to_failure_bundle,
)
from je_web_runner.utils.console_error_budget.budget import (
    ConsoleBudgetError, ConsoleMessage, BudgetReport, ErrorBudget, evaluate, from_selenium_log,
    from_cdp_console_events, from_cdp_exception_events,
)
from je_web_runner.utils.otel_bridge.trace_bridge import (
    TraceBridgeError, TraceContext, random_trace_context, parse_traceparent as otel_bridge_parse_traceparent,
    current_otel_context, inject_headers_selenium, clear_headers_selenium, inject_headers_playwright,
    clear_headers_playwright, bridged_span_selenium, bridged_span_playwright, trace_link,
)

__all__ = [
    "BackendLogCorrelatorError", "CorrelatedLog", "backend_log_correlator_parse_traceparent", "validate_trace_id",
    "fetch_file_log", "fetch_loki", "fetch_elasticsearch", "correlate", "attach_to_failure_bundle",
    "ConsoleBudgetError", "ConsoleMessage", "BudgetReport", "ErrorBudget", "evaluate", "from_selenium_log",
    "from_cdp_console_events", "from_cdp_exception_events", "TraceBridgeError", "TraceContext",
    "random_trace_context", "otel_bridge_parse_traceparent", "current_otel_context", "inject_headers_selenium",
    "clear_headers_selenium", "inject_headers_playwright", "clear_headers_playwright", "bridged_span_selenium",
    "bridged_span_playwright", "trace_link",
]
