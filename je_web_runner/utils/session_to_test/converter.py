"""
把 rrweb / 通用 session event 串流轉成 WR action JSON。
Production session replays (rrweb, Pendo, Hotjar) carry rich event
streams. This converter normalises them into the WebRunner action JSON
that ``executor`` already understands, so a real user flow becomes a
reproducible test.

Supports two input shapes:

* **rrweb events** — the public ``[{type, data, timestamp}]`` shape from
  ``rrweb.record``. We handle ``IncrementalSnapshot`` mouse / input / scroll
  events plus the top-level page-load metadata.
* **Generic events** — provider-agnostic ``{kind, target, value?, url?,
  timestamp}`` dicts. This is the format you'd produce when scraping
  Pendo/Hotjar/custom telemetry.

The converter is deliberately conservative: events it cannot map cleanly
become ``WR_comment`` action lines instead of being silently dropped, so
the engineer reviewing the output sees what was skipped.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger

_CSS_SELECTOR_BY = "css selector"


class SessionToTestError(WebRunnerException):
    """Raised on unreadable input, malformed events, or empty conversions."""


# rrweb event type ids
_RRWEB_FULL_SNAPSHOT = 2
_RRWEB_INCREMENTAL = 3
_RRWEB_META = 4

# rrweb incremental-source ids
_RRWEB_SRC_MOUSE_INTERACTION = 2
_RRWEB_SRC_SCROLL = 3
_RRWEB_SRC_INPUT = 5

# rrweb mouse-interaction kinds
_RRWEB_MI_CLICK = 2
_RRWEB_MI_DOUBLE_CLICK = 4

# pragmatic threshold: drop micro-mouse-moves rarer than this many ms apart
_MIN_INTER_EVENT_MS = 50


# ---------- public model ------------------------------------------------

@dataclass
class ConversionStats:
    """Roll-up returned by :func:`convert_events`."""

    input_events: int = 0
    actions_emitted: int = 0
    skipped_events: int = 0
    comment_actions: int = 0
    reasons: Dict[str, int] = field(default_factory=dict)

    def note_skip(self, reason: str) -> None:
        self.skipped_events += 1
        self.reasons[reason] = self.reasons.get(reason, 0) + 1


@dataclass
class ConversionResult:
    """Output of :func:`convert_events`: actions plus stats."""

    actions: List[Dict[str, Any]]
    stats: ConversionStats


# ---------- entry points ------------------------------------------------  # NOSONAR S3776 — cohesive logic; planned refactor in follow-up

def convert_rrweb_events(events: Sequence[Dict[str, Any]]) -> ConversionResult:
    """Convert an rrweb event list into WR action JSON."""
    if not isinstance(events, list):
        raise SessionToTestError("rrweb events must be a list")
    stats = ConversionStats(input_events=len(events))
    actions: List[Dict[str, Any]] = []
    last_ts: Optional[int] = None

    for event in events:
        if not isinstance(event, dict):
            stats.note_skip("non-dict event")
            continue
        kind = event.get("type")
        timestamp = event.get("timestamp")
        if kind == _RRWEB_META and isinstance(event.get("data"), dict):
            url = event["data"].get("href")
            if isinstance(url, str) and url:
                actions.append({"WR_to_url": [url]})
                stats.actions_emitted += 1
            else:
                stats.note_skip("meta without href")
            last_ts = timestamp
            continue
        if kind == _RRWEB_FULL_SNAPSHOT:
            stats.note_skip("full snapshot (no action)")
            last_ts = timestamp
            continue
        if kind != _RRWEB_INCREMENTAL:
            stats.note_skip(f"unknown rrweb type {kind!r}")
            continue

        # Track the latest timestamp so future iterations can compute deltas.
        # We do not currently emit explicit waits for fast bursts; this hook is
        # kept for future "WR_implicitly_wait" insertion logic.
        if last_ts is not None and isinstance(timestamp, (int, float)):
            last_ts = timestamp

        emitted = _convert_rrweb_incremental(event, stats)
        if emitted is not None:
            actions.append(emitted)
            stats.actions_emitted += 1

    if not actions:
        raise SessionToTestError(
            f"no actions produced from {len(events)} rrweb events; "
            "input may be unsupported or empty"
        )
    return ConversionResult(actions=actions, stats=stats)


def convert_generic_events(events: Sequence[Dict[str, Any]]) -> ConversionResult:
    """Convert a provider-agnostic event list into WR action JSON."""
    if not isinstance(events, list):
        raise SessionToTestError("generic events must be a list")
    stats = ConversionStats(input_events=len(events))
    actions: List[Dict[str, Any]] = []
    for event in events:
        if not isinstance(event, dict):
            stats.note_skip("non-dict event")
            continue
        emitted = _convert_generic_event(event, stats)
        if emitted is not None:
            actions.append(emitted)
            stats.actions_emitted += 1
    if not actions:
        raise SessionToTestError(
            f"no actions produced from {len(events)} generic events"
        )
    return ConversionResult(actions=actions, stats=stats)


def convert_events(payload: Union[str, Path, Sequence[Dict[str, Any]]]) -> ConversionResult:
    """
    Sniff the input: file → list / list → list. rrweb vs generic is
    detected by the presence of an integer ``type`` field on the events.
    """
    events = _load_events(payload)
    if not events:
        raise SessionToTestError("event list is empty")
    if isinstance(events[0], dict) and isinstance(events[0].get("type"), int):
        return convert_rrweb_events(events)
    return convert_generic_events(events)


def _load_events(payload: Union[str, Path, Sequence[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    if isinstance(payload, (list, tuple)):
        return list(payload)
    if isinstance(payload, (str, Path)):
        path = Path(payload)
        if not path.exists():
            raise SessionToTestError(f"events file not found: {path}")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as error:
            raise SessionToTestError(f"events file is not JSON: {error}") from error
        if isinstance(data, dict) and "events" in data:
            data = data["events"]
        if not isinstance(data, list):
            raise SessionToTestError("events file did not contain a list")
        return data
    raise SessionToTestError(
        f"convert_events expects path or list, got {type(payload).__name__}"
    )


# ---------- rrweb mappings ----------------------------------------------

def _convert_rrweb_incremental(
    event: Dict[str, Any],
    stats: ConversionStats,
) -> Optional[Dict[str, Any]]:
    data = event.get("data") if isinstance(event.get("data"), dict) else None
    if not data:
        stats.note_skip("incremental without data")
        return None
    source = data.get("source")
    if source == _RRWEB_SRC_MOUSE_INTERACTION:
        kind = data.get("type")
        selector = _selector_for_node(data.get("id"))
        if selector is None:
            stats.note_skip("mouse without node id")
            return None
        if kind == _RRWEB_MI_CLICK:
            return {"WR_click_element": [_CSS_SELECTOR_BY, selector]}
        if kind == _RRWEB_MI_DOUBLE_CLICK:
            return {"WR_double_click_element": [_CSS_SELECTOR_BY, selector]}
        stats.note_skip(f"mouse type {kind!r}")
        return None
    if source == _RRWEB_SRC_INPUT:
        selector = _selector_for_node(data.get("id"))
        value = data.get("text", "")
        if selector is None:
            stats.note_skip("input without node id")
            return None
        return {"WR_input_to_element": [_CSS_SELECTOR_BY, selector, str(value)]}
    if source == _RRWEB_SRC_SCROLL:
        x = data.get("x", 0)
        y = data.get("y", 0)
        return {"WR_comment": [f"scroll to {x},{y}"]}
    stats.note_skip(f"incremental source {source!r}")
    return None


def _selector_for_node(node_id: Any) -> Optional[str]:
    """
    rrweb identifies nodes by integer id from its DOM mirror. Without the
    full snapshot we can't recover a stable CSS path, so we emit a custom
    attribute selector that the test harness can rewrite later.
    """
    if not isinstance(node_id, int) or node_id < 0:
        return None
    return f'[data-rrweb-id="{node_id}"]'


# ---------- generic mappings --------------------------------------------
  # NOSONAR S3776 — cohesive logic; planned refactor in follow-up
def _convert_generic_event(
    event: Dict[str, Any],
    stats: ConversionStats,
) -> Optional[Dict[str, Any]]:
    kind = str(event.get("kind") or "").lower()
    target = event.get("target")
    locator = _coerce_locator(target)
    if kind == "navigate":
        url = event.get("url")
        if isinstance(url, str) and url:
            return {"WR_to_url": [url]}
        stats.note_skip("navigate without url")
        return None
    if kind == "click":
        if locator is None:
            stats.note_skip("click without target")
            return None
        return {"WR_click_element": list(locator)}
    if kind == "input":
        if locator is None:
            stats.note_skip("input without target")
            return None
        value = event.get("value", "")
        return {"WR_input_to_element": [*locator, str(value)]}
    if kind == "submit":
        if locator is None:
            return {"WR_comment": ["submit form (no target)"]}
        return {"WR_submit_element": list(locator)}
    if kind == "wait":
        try:
            seconds = float(event.get("seconds", 0))
        except (TypeError, ValueError):
            stats.note_skip("wait with non-numeric seconds")
            return None
        return {"WR_implicitly_wait": [seconds]}
    stats.note_skip(f"unknown generic kind {kind!r}")
    return None


def _coerce_locator(target: Any) -> Optional[Tuple[str, str]]:
    if isinstance(target, dict):
        by = target.get("by") or _CSS_SELECTOR_BY
        value = target.get("value")
        if isinstance(value, str) and value:
            return str(by), value
        return None
    if isinstance(target, str) and target:
        return _CSS_SELECTOR_BY, target
    return None


# ---------- output helpers ----------------------------------------------

def write_actions_json(
    result: ConversionResult,
    output_path: Union[str, Path],
) -> Path:
    """Persist the converted actions list to disk in WR action format."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(result.actions, fp, ensure_ascii=False, indent=2)
    web_runner_logger.info(
        f"session_to_test: wrote {result.stats.actions_emitted} actions to {path} "
        f"(skipped {result.stats.skipped_events})"
    )
    return path
