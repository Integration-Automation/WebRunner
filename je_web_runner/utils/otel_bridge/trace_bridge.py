"""
把 OpenTelemetry 的 trace context 注入到瀏覽器發出的 HTTP request header，
讓前端 → 後端的 distributed trace 串成一條。

Inject W3C ``traceparent`` / ``tracestate`` headers into every browser
request so a frontend action and the backend span it triggers land in
the same trace tree. Supports:

* **Selenium 4+ Chromium** — via CDP ``Network.setExtraHTTPHeaders``.
* **Playwright** — via ``page.set_extra_http_headers``.

If ``opentelemetry-api`` isn't installed (it's a soft dep), the helpers
fall back to caller-provided ``trace_id`` / ``span_id`` so callers using
some other tracing library can still bridge.
"""
from __future__ import annotations

import secrets
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Dict, Iterator, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class TraceBridgeError(WebRunnerException):
    """Raised when header injection or context propagation fails."""


# ---------- W3C traceparent helpers --------------------------------------

@dataclass(frozen=True)
class TraceContext:
    """W3C traceparent fields decoupled from any specific SDK."""

    trace_id: str  # 32 hex chars
    span_id: str  # 16 hex chars
    sampled: bool = True
    version: str = "00"
    tracestate: Optional[str] = None

    def to_traceparent(self) -> str:
        flags = "01" if self.sampled else "00"
        return f"{self.version}-{self.trace_id}-{self.span_id}-{flags}"

    def as_headers(self) -> Dict[str, str]:
        headers = {"traceparent": self.to_traceparent()}
        if self.tracestate:
            headers["tracestate"] = self.tracestate
        return headers


_HEX = "0123456789abcdef"


def _is_hex(value: str, length: int) -> bool:
    return (
        isinstance(value, str)
        and len(value) == length
        and all(ch in _HEX for ch in value)
    )


def _validate_context(ctx: TraceContext) -> None:
    if not _is_hex(ctx.trace_id, 32) or ctx.trace_id == "0" * 32:
        raise TraceBridgeError(f"invalid trace_id: {ctx.trace_id!r}")
    if not _is_hex(ctx.span_id, 16) or ctx.span_id == "0" * 16:
        raise TraceBridgeError(f"invalid span_id: {ctx.span_id!r}")
    if not _is_hex(ctx.version, 2):
        raise TraceBridgeError(f"invalid version: {ctx.version!r}")


def random_trace_context(sampled: bool = True) -> TraceContext:
    """Generate a fresh W3C-compliant trace context (for synthetic traces)."""
    return TraceContext(
        trace_id=secrets.token_hex(16),
        span_id=secrets.token_hex(8),
        sampled=sampled,
    )


def parse_traceparent(header: str) -> TraceContext:
    """Parse a ``traceparent`` header back into a :class:`TraceContext`."""
    if not isinstance(header, str):
        raise TraceBridgeError(f"traceparent must be str, got {type(header).__name__}")
    parts = header.strip().split("-")
    if len(parts) != 4:
        raise TraceBridgeError(f"malformed traceparent: {header!r}")
    version, trace_id, span_id, flags = parts
    sampled = bool(int(flags, 16) & 1) if _is_hex(flags, 2) else False
    ctx = TraceContext(
        trace_id=trace_id, span_id=span_id, sampled=sampled, version=version,
    )
    _validate_context(ctx)
    return ctx


# ---------- pull context from active OpenTelemetry span ------------------

def current_otel_context() -> Optional[TraceContext]:
    """
    若有 active OTel span 就把它包成 TraceContext；沒 OTel 或無 active span 回 None。
    Return the active OpenTelemetry span's context as a :class:`TraceContext`
    if OpenTelemetry is installed and a span is currently active. Returns
    ``None`` otherwise — callers should fall back to a synthetic context.
    """
    try:
        from opentelemetry import trace  # type: ignore[import-not-found]
    except ImportError:
        return None
    span = trace.get_current_span()
    if span is None:
        return None
    ctx = span.get_span_context()
    if not ctx or not getattr(ctx, "is_valid", False):
        return None
    trace_id_int = ctx.trace_id
    span_id_int = ctx.span_id
    if not trace_id_int or not span_id_int:
        return None
    flags = ctx.trace_flags if hasattr(ctx, "trace_flags") else 0
    return TraceContext(
        trace_id=format(trace_id_int, "032x"),
        span_id=format(span_id_int, "016x"),
        sampled=bool(int(flags) & 1),
    )


# ---------- header injection ---------------------------------------------

def inject_headers_selenium(driver: Any, context: TraceContext) -> None:
    """
    透過 CDP 把 traceparent / tracestate 加進 Chrome 每個 request。
    Use ``Network.setExtraHTTPHeaders`` via Selenium's CDP bridge to add
    the trace context to every outgoing browser request. Idempotent —
    calling again with a new context simply replaces the previous headers.
    """
    if driver is None:
        raise TraceBridgeError("driver is None")
    _validate_context(context)
    cdp = getattr(driver, "execute_cdp_cmd", None)
    if cdp is None:
        raise TraceBridgeError(
            "driver does not expose execute_cdp_cmd (need Selenium 4 + Chromium)"
        )
    headers = context.as_headers()
    try:
        cdp("Network.enable", {})
        cdp("Network.setExtraHTTPHeaders", {"headers": headers})
    except Exception as error:  # noqa: BLE001 — CDP errors are driver-specific
        raise TraceBridgeError(f"CDP header injection failed: {error!r}") from error
    web_runner_logger.info(
        f"inject_headers_selenium: trace_id={context.trace_id} span_id={context.span_id}"
    )


def clear_headers_selenium(driver: Any) -> None:
    """Remove the extra headers from the active Chrome session."""
    if driver is None:
        return
    cdp = getattr(driver, "execute_cdp_cmd", None)
    if cdp is None:
        return
    try:
        cdp("Network.setExtraHTTPHeaders", {"headers": {}})
    except Exception as error:  # noqa: BLE001
        web_runner_logger.warning(f"clear_headers_selenium failed: {error!r}")


def inject_headers_playwright(page: Any, context: TraceContext) -> None:
    """
    對 Playwright page 設 ``set_extra_http_headers``，附 traceparent。
    Equivalent to :func:`inject_headers_selenium` but for Playwright.
    """
    if page is None:
        raise TraceBridgeError("page is None")
    _validate_context(context)
    setter = getattr(page, "set_extra_http_headers", None)
    if setter is None:
        raise TraceBridgeError("page has no set_extra_http_headers method")
    try:
        setter(context.as_headers())
    except Exception as error:  # noqa: BLE001
        raise TraceBridgeError(f"Playwright header injection failed: {error!r}") from error
    web_runner_logger.info(
        f"inject_headers_playwright: trace_id={context.trace_id}"
    )


def clear_headers_playwright(page: Any) -> None:
    """Reset extra headers on a Playwright page."""
    if page is None:
        return
    setter = getattr(page, "set_extra_http_headers", None)
    if setter is None:
        return
    try:
        setter({})
    except Exception as error:  # noqa: BLE001
        web_runner_logger.warning(f"clear_headers_playwright failed: {error!r}")


# ---------- context managers --------------------------------------------

@contextmanager
def bridged_span_selenium(
    driver: Any,
    span_name: str,
    *,
    fallback_context: Optional[TraceContext] = None,
) -> Iterator[TraceContext]:
    """
    用 OTel span 包住一段 selenium 動作，並把 traceparent 注入瀏覽器。
    Start an OpenTelemetry span (when available) and inject its context
    into the active Chrome session for the duration of the ``with`` block.
    If OTel isn't installed, ``fallback_context`` is used (or a fresh
    synthetic context if both are missing).
    """
    span_ctx: Optional[Any] = None
    try:
        from opentelemetry import trace  # type: ignore[import-not-found]
        tracer = trace.get_tracer("je_web_runner.otel_bridge")
        span_ctx = tracer.start_as_current_span(span_name)
        span_ctx.__enter__()
        context = current_otel_context() or fallback_context or random_trace_context()
    except ImportError:
        context = fallback_context or random_trace_context()
    inject_headers_selenium(driver, context)
    try:
        yield context
    finally:
        clear_headers_selenium(driver)
        if span_ctx is not None:
            try:
                span_ctx.__exit__(None, None, None)
            except Exception as error:  # noqa: BLE001
                web_runner_logger.warning(f"span exit failed: {error!r}")


@contextmanager
def bridged_span_playwright(
    page: Any,
    span_name: str,
    *,
    fallback_context: Optional[TraceContext] = None,
) -> Iterator[TraceContext]:
    """Playwright twin of :func:`bridged_span_selenium`."""
    span_ctx: Optional[Any] = None
    try:
        from opentelemetry import trace  # type: ignore[import-not-found]
        tracer = trace.get_tracer("je_web_runner.otel_bridge")
        span_ctx = tracer.start_as_current_span(span_name)
        span_ctx.__enter__()
        context = current_otel_context() or fallback_context or random_trace_context()
    except ImportError:
        context = fallback_context or random_trace_context()
    inject_headers_playwright(page, context)
    try:
        yield context
    finally:
        clear_headers_playwright(page)
        if span_ctx is not None:
            try:
                span_ctx.__exit__(None, None, None)
            except Exception as error:  # noqa: BLE001
                web_runner_logger.warning(f"span exit failed: {error!r}")


# ---------- report helpers ----------------------------------------------

def trace_link(
    context: TraceContext,
    *,
    jaeger_base: Optional[str] = None,
    tempo_base: Optional[str] = None,
) -> Optional[str]:
    """
    給定 trace context 與後端 base URL，回傳可點擊的 trace 連結。
    Build a direct UI link to the trace in Jaeger / Tempo. Returns the
    first base URL that's provided. ``None`` if no base is supplied.
    """
    if jaeger_base:
        base = jaeger_base.rstrip("/")
        return f"{base}/trace/{context.trace_id}"
    if tempo_base:
        base = tempo_base.rstrip("/")
        return f"{base}/explore?orgId=1&left=%7B%22queries%22:%5B%7B%22query%22:%22{context.trace_id}%22%7D%5D%7D"
    return None
