"""
OpenTelemetry traces：每個 ``WR_*`` action 包進一個 span。
OpenTelemetry tracing for the executor. Each action becomes a span, so
runs can be inspected in Jaeger / Tempo / OTLP-compatible UIs.

``opentelemetry-sdk`` 為軟相依；未安裝時會丟出含安裝提示的錯誤。
``opentelemetry-sdk`` is a soft dependency; missing imports raise a
clear install hint.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, ContextManager

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class OTelTracingError(WebRunnerException):
    """Raised when OpenTelemetry isn't available or installation fails."""


_tracer: Any = None


def _require_otel():
    try:
        from opentelemetry import trace  # type: ignore[import-not-found]
        from opentelemetry.sdk.resources import Resource  # type: ignore[import-not-found]
        from opentelemetry.sdk.trace import TracerProvider  # type: ignore[import-not-found]
        from opentelemetry.sdk.trace.export import (  # type: ignore[import-not-found]
            BatchSpanProcessor,
            ConsoleSpanExporter,
            SimpleSpanProcessor,
        )
        return trace, Resource, TracerProvider, BatchSpanProcessor, SimpleSpanProcessor, ConsoleSpanExporter
    except ImportError as error:
        raise OTelTracingError(
            "opentelemetry-sdk is not installed. "
            "Install with: pip install opentelemetry-sdk"
        ) from error


def init_tracer(
    service_name: str = "webrunner",
    use_console_exporter: bool = True,
    span_processor: Any = None,
) -> Any:
    """
    建立 ``TracerProvider`` 並安裝；回傳 ``Tracer``
    Configure a TracerProvider once, attach the requested span processor
    (a ConsoleSpanExporter by default for easy verification), and return a
    Tracer scoped to ``service_name``.
    """
    global _tracer
    web_runner_logger.info(f"init_tracer service={service_name}")
    # The names below are real classes from opentelemetry-sdk; the
    # ``CamelCase`` in lower-scope is unavoidable (SonarCloud S117 false
    # positive on import aliases).
    (
        trace,
        resource_cls,
        tracer_provider_cls,
        _batch_processor_cls,  # imported for completeness; not used here
        simple_processor_cls,
        console_exporter_cls,
    ) = _require_otel()
    provider = tracer_provider_cls(
        resource=resource_cls.create({"service.name": service_name})
    )
    if span_processor is not None:
        provider.add_span_processor(span_processor)
    elif use_console_exporter:
        provider.add_span_processor(simple_processor_cls(console_exporter_cls()))
    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer(service_name)
    return _tracer


def reset_tracer() -> None:
    """Drop the cached tracer (mainly for tests)."""
    global _tracer
    _tracer = None


def install_executor_tracing(
    service_name: str = "webrunner",
    use_console_exporter: bool = True,
) -> Any:
    """
    在全域 executor 上安裝「每 action 一個 span」的 hook
    Install a span factory on the singleton executor so every action becomes
    a span. Returns the configured tracer for further customisation.
    """
    tracer = init_tracer(service_name, use_console_exporter=use_console_exporter)

    @contextmanager
    def _factory(name: str) -> ContextManager:
        with tracer.start_as_current_span(name):
            yield

    # Imported lazily to avoid circular import (executor module ← this module).
    from je_web_runner.utils.executor.action_executor import executor
    executor.set_action_span_factory(_factory)
    return tracer


def uninstall_executor_tracing() -> None:
    """Remove the span factory from the executor."""
    from je_web_runner.utils.executor.action_executor import executor
    executor.set_action_span_factory(None)
