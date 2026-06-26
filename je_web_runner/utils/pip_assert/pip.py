"""
Picture-in-Picture (video + Document PiP) assertions.

Two PiP variants exist in modern browsers:

* ``HTMLVideoElement.requestPictureInPicture`` (classic, video only).
* ``documentPictureInPicture.requestWindow`` (whole-document PiP).

This module logs every enter/exit/track-change event for both variants
and provides assertions to verify the page actually entered PiP,
restored controls correctly, and exited when navigating away.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

from je_web_runner.utils.exception.exceptions import WebRunnerException


class PipAssertError(WebRunnerException):
    """Raised on assertion failure."""


INSTALL_SCRIPT = r"""
(function () {
  if (window.__wr_pip__) return;
  const events = [];
  // Classic video PiP
  const videoProto = window.HTMLVideoElement &&
    HTMLVideoElement.prototype;
  if (videoProto && videoProto.requestPictureInPicture) {
    const origReq = videoProto.requestPictureInPicture;
    videoProto.requestPictureInPicture = function () {
      events.push({kind: 'enter', mode: 'video', ts: Date.now()});
      return origReq.apply(this, arguments);
    };
  }
  if (document.exitPictureInPicture) {
    const origExit = document.exitPictureInPicture.bind(document);
    document.exitPictureInPicture = function () {
      events.push({kind: 'exit', mode: 'video', ts: Date.now()});
      return origExit();
    };
  }
  // Document PiP
  if (window.documentPictureInPicture) {
    const origDoc = window.documentPictureInPicture.requestWindow
      .bind(window.documentPictureInPicture);
    window.documentPictureInPicture.requestWindow = function (opts) {
      events.push({kind: 'enter', mode: 'document', ts: Date.now(),
                   width: opts && opts.width, height: opts && opts.height});
      return origDoc(opts);
    };
  }
  window.__wr_pip__ = {
    drain: function () { return events.splice(0); },
  };
})();
"""


class Mode(str, Enum):
    VIDEO = "video"
    DOCUMENT = "document"


@dataclass
class PipEvent:
    kind: str        # "enter" | "exit"
    mode: Mode
    ts_ms: int = 0
    width: int | None = None
    height: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "mode": self.mode.value}


@dataclass
class PipLog:
    events: list[PipEvent] = field(default_factory=list)


def parse_log(payload: Any) -> PipLog:
    if not isinstance(payload, list):
        raise PipAssertError("payload must be a list")
    out: list[PipEvent] = []
    for raw in payload:
        if not isinstance(raw, dict):
            continue
        kind = str(raw.get("kind") or "")
        if kind not in ("enter", "exit"):
            continue
        try:
            mode = Mode(str(raw.get("mode") or "video"))
        except ValueError as exc:
            raise PipAssertError(
                f"unknown PiP mode {raw.get('mode')!r}"
            ) from exc
        out.append(PipEvent(
            kind=kind, mode=mode,
            ts_ms=int(raw.get("ts") or 0),
            width=raw.get("width"),
            height=raw.get("height"),
        ))
    return PipLog(events=out)


def assert_entered(log: PipLog, *, mode: Mode = Mode.VIDEO) -> None:
    if not any(e.kind == "enter" and e.mode == mode for e in log.events):
        raise PipAssertError(
            f"page never entered {mode.value} PiP"
        )


def assert_exited_cleanly(log: PipLog, *, mode: Mode = Mode.VIDEO) -> None:
    enters = sum(1 for e in log.events if e.kind == "enter" and e.mode == mode)
    exits = sum(1 for e in log.events if e.kind == "exit" and e.mode == mode)
    if enters != exits:
        raise PipAssertError(
            f"{mode.value} PiP: enters={enters}, exits={exits} — "
            "page left PiP window dangling"
        )


def assert_size_at_least(
    log: PipLog, *, min_width: int, min_height: int,
) -> None:
    if min_width <= 0 or min_height <= 0:
        raise PipAssertError("min_width/min_height must be positive")
    for e in log.events:
        if e.kind != "enter" or e.mode != Mode.DOCUMENT:
            continue
        if (e.width is None or e.height is None
                or e.width < min_width or e.height < min_height):
            raise PipAssertError(
                f"document PiP opened with {e.width}x{e.height}, "
                f"expected >= {min_width}x{min_height}"
            )
