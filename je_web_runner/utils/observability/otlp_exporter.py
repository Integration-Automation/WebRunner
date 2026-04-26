"""
OTLP exporter 整合：把既有的 OTel tracing 接到 Jaeger / Tempo / OTLP-grpc 後端。
Wire the existing :mod:`otel_tracing` setup to a real OTLP backend.

The exporter is purely additive — :func:`configure_otlp_export` builds
an ``OTLPSpanExporter`` (gRPC by default, HTTP fallback) and registers a
``BatchSpanProcessor`` on the supplied ``TracerProvider``.  Both the gRPC
and HTTP exporters live in soft-dep packages; missing imports raise a
clear install hint.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException


class OtlpExporterError(WebRunnerException):
    """Raised when configuration is invalid or the SDK is missing."""


@dataclass
class OtlpExportConfig:
    """Caller-supplied OTLP wiring."""

    endpoint: str
    protocol: str = "grpc"  # "grpc" | "http"
    headers: Optional[Dict[str, str]] = None
    timeout: float = 10.0
    insecure: bool = False
    service_name: str = "webrunner"

    def __post_init__(self) -> None:
        if not isinstance(self.endpoint, str) or not self.endpoint:
            raise OtlpExporterError("endpoint must be a non-empty string")
        if self.protocol not in {"grpc", "http"}:
            raise OtlpExporterError(
                f"protocol must be 'grpc' / 'http', got {self.protocol!r}"
            )
        if self.timeout <= 0:
            raise OtlpExporterError("timeout must be > 0")


def _import_grpc_exporter():
    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (  # type: ignore[import-not-found]
            OTLPSpanExporter,
        )
        return OTLPSpanExporter
    except ImportError as error:
        raise OtlpExporterError(
            "opentelemetry-exporter-otlp-proto-grpc is not installed. "
            "Install with: pip install opentelemetry-exporter-otlp"
        ) from error


def _import_http_exporter():
    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (  # type: ignore[import-not-found]
            OTLPSpanExporter,
        )
        return OTLPSpanExporter
    except ImportError as error:
        raise OtlpExporterError(
            "opentelemetry-exporter-otlp-proto-http is not installed. "
            "Install with: pip install opentelemetry-exporter-otlp"
        ) from error


def _import_batch_processor():
    try:
        from opentelemetry.sdk.trace.export import BatchSpanProcessor  # type: ignore[import-not-found]
        return BatchSpanProcessor
    except ImportError as error:
        raise OtlpExporterError(
            "opentelemetry-sdk is not installed. "
            "Install with: pip install opentelemetry-sdk"
        ) from error


def build_exporter(config: OtlpExportConfig) -> Any:
    """Construct an ``OTLPSpanExporter`` matching the requested protocol."""
    if config.protocol == "grpc":
        cls = _import_grpc_exporter()
        return cls(
            endpoint=config.endpoint,
            headers=tuple((config.headers or {}).items()) or None,
            timeout=config.timeout,
            insecure=config.insecure,
        )
    cls = _import_http_exporter()
    return cls(
        endpoint=config.endpoint,
        headers=config.headers or None,
        timeout=config.timeout,
    )


def configure_otlp_export(
    tracer_provider: Any,
    config: OtlpExportConfig,
    processor_factory: Optional[Any] = None,
    exporter_factory: Optional[Any] = None,
) -> Any:
    """
    Build the exporter + ``BatchSpanProcessor`` and register it with the
    supplied ``TracerProvider``. Returns the registered processor so the
    caller can call ``shutdown()`` cleanly.

    ``processor_factory`` / ``exporter_factory`` let unit tests inject
    stubs without importing the OTel SDK.
    """
    if not hasattr(tracer_provider, "add_span_processor"):
        raise OtlpExporterError(
            "tracer_provider must expose add_span_processor() (OTel SDK shape)"
        )
    exporter = (exporter_factory or build_exporter)(config)
    processor_cls = processor_factory or _import_batch_processor()
    processor = processor_cls(exporter)
    tracer_provider.add_span_processor(processor)
    return processor
