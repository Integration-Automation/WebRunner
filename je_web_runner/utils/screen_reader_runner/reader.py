"""
從 accessibility tree 模擬 NVDA / VoiceOver 朗讀順序與斷句。
Real-screen-reader testing on CI is fragile (audio capture, OS quirks);
this module skips the audio loop entirely and walks the accessibility
tree to reproduce *what* a screen reader would say and *in what order*.

Two outputs:

* **utterances** — the sequence of strings a SR would announce as you
  press Tab / arrow-down through the page.
* **violations** — common a11y red flags that surface during the walk
  (interactive element with no accessible name, heading skip, image
  without alt, link text "click here").

Driver-agnostic: feed in a JSON accessibility tree (CDP's
``Accessibility.getFullAXTree``, Playwright's ``page.accessibility.snapshot()``,
or Selenium's WebDriver BiDi `browsingContext.captureAccessibilityTree`).
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List

from je_web_runner.utils.exception.exceptions import WebRunnerException


class ScreenReaderError(WebRunnerException):
    """Raised on malformed accessibility tree input."""


# Roles SRs typically announce / focus on. Anything else is treated as
# decorative / structural.
_INTERACTIVE_ROLES = {
    "button", "link", "checkbox", "radio", "textbox", "combobox",
    "menuitem", "tab", "switch", "spinbutton", "slider", "searchbox",
}

_GROUPING_ROLES = {
    "heading", "list", "listitem", "navigation", "main", "banner",
    "region", "complementary", "contentinfo", "form", "article",
}

# Phrases banned in link names (well-known a11y anti-patterns)
_BANNED_LINK_TEXT = ("click here", "here", "more", "read more", "link")


# ---------- enums -------------------------------------------------------

class ViolationKind(str, Enum):
    """Categories of a11y issues this module surfaces."""

    UNNAMED_INTERACTIVE = "unnamed_interactive"
    HEADING_SKIP = "heading_skip"
    MISSING_ALT = "missing_alt"
    GENERIC_LINK_TEXT = "generic_link_text"
    EMPTY_BUTTON = "empty_button"


# ---------- data --------------------------------------------------------

@dataclass
class Utterance:
    """One thing a screen reader would speak."""

    text: str
    role: str
    node_index: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Violation:
    """One a11y violation discovered during the walk."""

    kind: ViolationKind
    role: str
    node_index: int
    detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {**asdict(self), "kind": self.kind.value}


@dataclass
class ScreenReaderTranscript:
    """Result of :func:`walk_tree`."""

    utterances: List[Utterance] = field(default_factory=list)
    violations: List[Violation] = field(default_factory=list)

    def speech(self) -> str:
        """Joined transcript as a single string."""
        return " ".join(u.text for u in self.utterances if u.text)

    def passed(self) -> bool:
        return not self.violations


# ---------- walker ------------------------------------------------------

def walk_tree(
    root: Dict[str, Any],
    *,
    include_decorative: bool = False,
) -> ScreenReaderTranscript:
    """
    Walk an accessibility tree (Playwright snapshot or CDP-shaped) and
    return the SR transcript. Schema: nodes have ``role`` and ``name``
    strings plus an optional ``children`` list.
    """
    if not isinstance(root, dict):
        raise ScreenReaderError(
            f"walk_tree expects dict, got {type(root).__name__}"
        )
    transcript = ScreenReaderTranscript()
    state = {"index": 0, "last_heading_level": 0}
    _walk_node(root, transcript, state, include_decorative=include_decorative)
    return transcript


def _walk_node(  # NOSONAR S3776 — cohesive logic; planned refactor in follow-up
    node: Dict[str, Any],
    transcript: ScreenReaderTranscript,
    state: Dict[str, int],
    *,
    include_decorative: bool,
) -> None:
    role = str(node.get("role") or "").lower()
    name = str(node.get("name") or "").strip()
    index = state["index"]
    state["index"] += 1

    if role == "heading":
        level = int(node.get("level") or 1)
        _check_heading_level(level, index, state, transcript)
        if name:
            transcript.utterances.append(Utterance(
                text=f"heading level {level}: {name}",
                role=role, node_index=index,
            ))
        state["last_heading_level"] = level
    elif role == "image":
        alt = name or str(node.get("description") or "").strip()
        if not alt and not _is_decorative(node):
            transcript.violations.append(Violation(
                kind=ViolationKind.MISSING_ALT,
                role=role, node_index=index,
            ))
        elif alt:
            transcript.utterances.append(Utterance(
                text=f"image: {alt}", role=role, node_index=index,
            ))
    elif role in _INTERACTIVE_ROLES:
        _emit_interactive(node, role, name, index, transcript)
    elif role in _GROUPING_ROLES:
        if name:
            transcript.utterances.append(Utterance(
                text=f"{role}: {name}", role=role, node_index=index,
            ))
    elif name and (include_decorative or role in {"text", "static_text", "statictext", ""}):
        if name:
            transcript.utterances.append(Utterance(
                text=name, role=role or "text", node_index=index,
            ))

    children = node.get("children") or []
    if not isinstance(children, list):
        return
    for child in children:
        if isinstance(child, dict):
            _walk_node(child, transcript, state,
                       include_decorative=include_decorative)


def _emit_interactive(
    _node: Dict[str, Any],
    role: str,
    name: str,
    index: int,
    transcript: ScreenReaderTranscript,
) -> None:
    if not name:
        transcript.violations.append(Violation(
            kind=ViolationKind.UNNAMED_INTERACTIVE,
            role=role, node_index=index,
            detail=f"{role} has no accessible name",
        ))
        if role == "button":
            transcript.violations.append(Violation(
                kind=ViolationKind.EMPTY_BUTTON,
                role=role, node_index=index,
            ))
        return
    if role == "link" and _is_generic_link(name):
        transcript.violations.append(Violation(
            kind=ViolationKind.GENERIC_LINK_TEXT,
            role=role, node_index=index,
            detail=f"link text {name!r} is non-descriptive",
        ))
    transcript.utterances.append(Utterance(
        text=f"{role}: {name}", role=role, node_index=index,
    ))


def _is_generic_link(name: str) -> bool:
    cleaned = re.sub(r"[\W_]+", " ", name).strip().lower()
    return cleaned in _BANNED_LINK_TEXT


def _is_decorative(node: Dict[str, Any]) -> bool:
    if node.get("decorative") is True:
        return True
    properties = node.get("properties") or {}
    if isinstance(properties, dict):
        if properties.get("presentational") is True:
            return True
        if properties.get("role") == "presentation":
            return True
    return False


def _check_heading_level(
    level: int,
    index: int,
    state: Dict[str, int],
    transcript: ScreenReaderTranscript,
) -> None:
    last = state["last_heading_level"]
    if last and level > last + 1:
        transcript.violations.append(Violation(
            kind=ViolationKind.HEADING_SKIP,
            role="heading",
            node_index=index,
            detail=f"jumped from h{last} to h{level}",
        ))


# ---------- assertion helpers -------------------------------------------

def assert_no_violations(transcript: ScreenReaderTranscript) -> None:
    """Raise unless the transcript has zero violations."""
    if not isinstance(transcript, ScreenReaderTranscript):
        raise ScreenReaderError("assert_no_violations expects ScreenReaderTranscript")
    if transcript.passed():
        return
    parts = ", ".join(
        f"{v.kind.value}@{v.node_index}" for v in transcript.violations[:5]
    )
    more = "" if len(transcript.violations) <= 5 else f" (+{len(transcript.violations) - 5})"
    raise ScreenReaderError(f"a11y violations: {parts}{more}")


def assert_reads(
    transcript: ScreenReaderTranscript,
    expected_phrase: str,
) -> Utterance:
    """Raise unless ``expected_phrase`` appears in any utterance."""
    if not isinstance(expected_phrase, str) or not expected_phrase:
        raise ScreenReaderError("expected_phrase must be a non-empty string")
    for utterance in transcript.utterances:
        if expected_phrase.lower() in utterance.text.lower():
            return utterance
    raise ScreenReaderError(
        f"SR transcript never contained {expected_phrase!r}"
    )
