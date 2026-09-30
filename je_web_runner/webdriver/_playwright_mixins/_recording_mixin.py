"""Trace viewer 與錄影 / Playwright tracing (trace viewer) and video recording."""
from __future__ import annotations

from typing import Any

from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.webdriver._playwright_mixins._common import PlaywrightBackendError, recorded


class _RecordingMixin:
    """Trace-viewer traces and video recordings of the current context.

    Tracing runs in chunks: :meth:`save_trace_chunk` writes what was recorded so far
    and keeps tracing, which is how the executor saves a trace beside each failure
    screenshot. A context rebuild (timezone, emulation …) restarts tracing on the new
    context with the same options; the part recorded before the rebuild is not saved.
    Videos are files Playwright finishes when their page's context closes, so
    :meth:`stop_video_recording` rebuilds the context and returns their paths.
    """

    @property
    def tracing_active(self) -> bool:
        """True between :meth:`start_tracing` and :meth:`stop_tracing`."""
        return self._trace_options is not None

    def _require_tracing(self) -> None:
        if self._trace_options is None:
            raise PlaywrightBackendError("Playwright tracing is not running; call start_tracing() first")

    @recorded()
    def start_tracing(self, screenshots: bool = True, snapshots: bool = True, sources: bool = False) -> None:
        """
        開始記錄 trace（可用 ``playwright show-trace`` 開啟）
        Start recording a trace of the current context for Playwright's trace viewer.
        """
        options = {"screenshots": screenshots, "snapshots": snapshots, "sources": sources}
        web_runner_logger.info(f"playwright start_tracing: {options}")
        self.context.tracing.start(**options)
        self.context.tracing.start_chunk()
        self._trace_options = options

    def save_trace_chunk(self, path: str) -> str:
        """Write the trace recorded since the last save to ``path`` and keep tracing."""
        self._require_tracing()
        self.context.tracing.stop_chunk(path=path)
        self.context.tracing.start_chunk()
        return path

    @recorded()
    def stop_tracing(self, path: str) -> str:
        """Write the trace recorded since the last save to ``path`` and stop tracing."""
        self._require_tracing()
        self.context.tracing.stop_chunk(path=path)
        self.context.tracing.stop()
        self._trace_options = None
        return path

    def _restart_tracing(self, context: Any) -> None:
        """Continue tracing on a freshly opened context (called by ``_open_context``)."""
        if self._trace_options is None:
            return
        context.tracing.start(**self._trace_options)
        context.tracing.start_chunk()

    @recorded()
    def start_video_recording(self, video_dir: str, width: int | None = None, height: int | None = None) -> None:
        """
        開始錄影（重建 context）
        Rebuild the context with video recording into ``video_dir``; ``width`` and
        ``height`` set the video size (Playwright scales the viewport to fit by default).
        """
        self._context_options["record_video_dir"] = video_dir
        if width and height:
            self._context_options["record_video_size"] = {"width": width, "height": height}
        else:
            self._context_options.pop("record_video_size", None)
        self._rebuild_context()

    @recorded()
    def stop_video_recording(self) -> list[str]:
        """
        停止錄影並回傳影片路徑
        Stop recording: close the context, which finishes the video files, continue in
        one without video, and return the files' paths (one per page that was open).
        """
        paths = [str(page.video.path()) for page in self._pages if getattr(page, "video", None)]
        self._context_options.pop("record_video_dir", None)
        self._context_options.pop("record_video_size", None)
        self._rebuild_context()
        return paths
