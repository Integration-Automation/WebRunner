"""
``<dialog>`` / ``popover`` open-close / invoker-binding assertions.
The HTML Popover API + ``<dialog>`` element behave subtly differently
from a CSS-only "show/hide" — light-dismiss, top-layer placement,
ESC handling, focus trap — and existing visual-diff tests miss
regressions in those.

This module exposes a small snapshot model (:class:`PopoverState`) plus
helpers that take a snapshot the caller harvested via CDP / JS and
assert what *should* be visible / on the top layer / pointing at which
invoker.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException


class PopoverAssertError(WebRunnerException):
    """Raised on malformed snapshot or failed assertion."""


class PopoverKind(str, Enum):
    """The two flavors the spec defines."""

    DIALOG = "dialog"
    POPOVER_AUTO = "auto"
    POPOVER_MANUAL = "manual"
    POPOVER_HINT = "hint"


HARVEST_SCRIPT = """
(function() {
  function describe(el) {
    const tag = el.tagName.toLowerCase();
    let kind = null;
    if (tag === 'dialog') kind = 'dialog';
    else if (el.hasAttribute('popover')) {
      const v = (el.getAttribute('popover') || 'auto').toLowerCase();
      kind = ['auto', 'manual', 'hint'].includes(v) ? v : 'auto';
    } else return null;
    const isOpen = (tag === 'dialog')
      ? el.open
      : (el.matches(':popover-open'));
    return {
      kind: kind,
      id: el.id || null,
      role: el.getAttribute('role') || null,
      open: !!isOpen,
      modal: tag === 'dialog' ? !!el.matches(':modal') : false,
      invoker: el.dataset && el.dataset.invokerId ? el.dataset.invokerId : null,
      bounding_rect: el.getBoundingClientRect ? (function() {
        const r = el.getBoundingClientRect();
        return {x: r.x, y: r.y, w: r.width, h: r.height};
      })() : null
    };
  }
  return Array.from(document.querySelectorAll('dialog,[popover]'))
    .map(describe)
    .filter(Boolean);
})();
""".strip()


# ---------- model -------------------------------------------------------

@dataclass
class PopoverState:
    """Snapshot of one ``<dialog>`` or ``[popover]`` element."""

    kind: PopoverKind
    open: bool
    id: Optional[str] = None
    role: Optional[str] = None
    modal: bool = False
    invoker: Optional[str] = None
    bounding_rect: Optional[Dict[str, float]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {**asdict(self), "kind": self.kind.value}


def parse_snapshot(payload: Any) -> List[PopoverState]:
    """Parse the harvested ``HARVEST_SCRIPT`` payload."""
    if not isinstance(payload, list):
        raise PopoverAssertError(
            f"snapshot must be a list, got {type(payload).__name__}"
        )
    out: List[PopoverState] = []
    for raw in payload:
        if not isinstance(raw, dict):
            continue
        try:
            kind = PopoverKind(str(raw.get("kind") or "auto"))
        except ValueError as error:
            raise PopoverAssertError(f"unknown popover kind: {error}") from error
        out.append(PopoverState(
            kind=kind,
            open=bool(raw.get("open", False)),
            id=raw.get("id"),
            role=raw.get("role"),
            modal=bool(raw.get("modal", False)),
            invoker=raw.get("invoker"),
            bounding_rect=raw.get("bounding_rect"),
        ))
    return out


# ---------- assertions --------------------------------------------------

def assert_open(states: Iterable[PopoverState], *, id_: str) -> PopoverState:
    """Assert popover/dialog with id is open."""
    if not isinstance(id_, str) or not id_:
        raise PopoverAssertError("id_ must be non-empty string")
    for state in states:
        if state.id == id_:
            if not state.open:
                raise PopoverAssertError(f"popover #{id_} exists but is closed")
            return state
    raise PopoverAssertError(f"no popover with id #{id_} in snapshot")


def assert_closed(states: Iterable[PopoverState], *, id_: str) -> None:
    """Assert no popover with id is open."""
    for state in states:
        if state.id == id_ and state.open:
            raise PopoverAssertError(f"popover #{id_} is unexpectedly open")


def assert_only_one_modal(states: Iterable[PopoverState]) -> None:
    """Assert at most one ``<dialog>`` is modal at a time (spec invariant)."""
    modal = [s for s in states if s.modal]
    if len(modal) > 1:
        ids = [s.id or "(unnamed)" for s in modal]
        raise PopoverAssertError(
            f"multiple modal dialogs open: {ids}"
        )


def assert_invoker_link(
    states: Iterable[PopoverState], *, popover_id: str, invoker_id: str,
) -> None:
    """Assert that ``popover_id``'s ``invoker`` data attr matches ``invoker_id``."""
    for state in states:
        if state.id != popover_id:
            continue
        if state.invoker != invoker_id:
            raise PopoverAssertError(
                f"popover #{popover_id} invoker is {state.invoker!r}, "
                f"want {invoker_id!r}"
            )
        return
    raise PopoverAssertError(f"no popover with id #{popover_id}")


def assert_no_open(states: Iterable[PopoverState]) -> None:
    """Assert there is no open popover or dialog (post-dismiss check)."""
    open_states = [s for s in states if s.open]
    if open_states:
        names = [s.id or s.kind.value for s in open_states]
        raise PopoverAssertError(f"expected no open popovers, got: {names}")
