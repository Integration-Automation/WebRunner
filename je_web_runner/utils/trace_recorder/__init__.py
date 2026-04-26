"""Playwright tracing wrapper that always produces a debuggable zip."""
from je_web_runner.utils.trace_recorder.recorder import (
    TraceRecorder,
    TraceRecorderError,
)

__all__ = ["TraceRecorder", "TraceRecorderError"]
