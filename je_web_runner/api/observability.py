"""Façade: timeline / failure bundle / memory leak / trace / cdp tap / event bus / OTLP."""
from je_web_runner.utils.bidi_backend.bridge import (
    BidiBackendError,
    BidiBridge,
    BidiEvent,
    BidiSubscription,
)
from je_web_runner.utils.cdp_tap.tap import (
    CdpRecord,
    CdpRecorder,
    CdpReplayer,
    CdpTapError,
    load_recording,
)
from je_web_runner.utils.event_bus.bus import (
    EventBus,
    EventBusError,
    EventEnvelope,
)
from je_web_runner.utils.failure_bundle.bundle import (
    FailureBundle,
    FailureBundleError,
    extract_bundle,
)
from je_web_runner.utils.memory_leak.detector import (
    MemoryLeakError,
    MemorySample,
    detect_growth,
    sample_used_heap,
)
from je_web_runner.utils.observability.timeline import (
    TimelineError,
    TimelineEvent,
    build,
    from_console,
    from_responses,
    from_spans,
    merge,
    to_dicts,
)
from je_web_runner.utils.observability.otlp_exporter import (
    OtlpExportConfig,
    OtlpExporterError,
    build_exporter,
    configure_otlp_export,
)
from je_web_runner.utils.trace_recorder.recorder import (
    TraceRecorder,
    TraceRecorderError,
)

__all__ = [
    "BidiBackendError", "BidiBridge", "BidiEvent", "BidiSubscription",
    "CdpRecord", "CdpRecorder", "CdpReplayer", "CdpTapError", "load_recording",
    "EventBus", "EventBusError", "EventEnvelope",
    "FailureBundle", "FailureBundleError", "extract_bundle",
    "MemoryLeakError", "MemorySample", "detect_growth", "sample_used_heap",
    "TimelineError", "TimelineEvent",
    "build", "from_console", "from_responses", "from_spans", "merge", "to_dicts",
    "OtlpExportConfig", "OtlpExporterError", "build_exporter", "configure_otlp_export",
    "TraceRecorder", "TraceRecorderError",
]
