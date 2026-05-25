"""
Reverse-engineer a human description of what a JSON action script does.

Given a list of WebRunner action steps, emit a Gherkin-ish ``Given / When /
Then`` paragraph. Useful for:

* PR reviewers without selenium knowledge.
* JIRA / Confluence "what this test covers" sections.
* Sanity-check that a freshly recorded test is actually doing what its
  filename claims.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class SelfDescribeError(WebRunnerException):
    """Raised on malformed action input."""


# action verb → category
_NAVIGATION = {"to_url", "open", "navigate", "back", "forward", "refresh"}
_INPUT = {"input_to_element", "send_keys", "type", "set_value"}
_CLICK = {"click_element", "click", "double_click", "right_click"}
_WAIT = {"wait", "implicit_wait", "explicit_wait", "wait_visible", "wait_clickable"}
_ASSERT = {"assert_text", "assert_visible", "assert_value", "assert_url"}
_SCROLL = {"scroll_to_element", "scroll_to", "scroll"}


@dataclass
class StepSummary:
    phase: str          # "Given" | "When" | "Then"
    sentence: str       # natural-language sentence


def _step_kind(action: Dict[str, Any]) -> str:
    name = (action.get("action_name") or action.get("function") or "").lower()
    if name in _NAVIGATION:
        return "navigation"
    if name in _INPUT:
        return "input"
    if name in _CLICK:
        return "click"
    if name in _WAIT:
        return "wait"
    if name in _ASSERT:
        return "assert"
    if name in _SCROLL:
        return "scroll"
    return "other"


def _locator_phrase(action: Dict[str, Any]) -> str:
    target = (action.get("element_name") or action.get("test_object")
              or action.get("locator") or action.get("by_value") or "")
    if not target:
        return "an element"
    return f'"{target}"'


def _sentence_for(action: Dict[str, Any]) -> StepSummary:
    kind = _step_kind(action)
    name = (action.get("action_name") or action.get("function") or "").lower()
    if kind == "navigation":
        url = action.get("url") or action.get("value") or ""
        if url:
            return StepSummary("Given", f"the user opens {url}")
        if name in ("back", "forward", "refresh"):
            return StepSummary("When", f"the user presses {name} in the browser")
        return StepSummary("Given", "the user opens the application")
    if kind == "input":
        text = action.get("input_value") or action.get("value") or ""
        return StepSummary(
            "When",
            f'the user types "{text}" into {_locator_phrase(action)}',
        )
    if kind == "click":
        return StepSummary("When", f"the user clicks {_locator_phrase(action)}")
    if kind == "wait":
        seconds = action.get("timeout") or action.get("value") or ""
        return StepSummary(
            "When",
            f"the user waits for {_locator_phrase(action)}"
            + (f" up to {seconds}s" if seconds else ""),
        )
    if kind == "assert":
        expected = action.get("expected") or action.get("value") or ""
        return StepSummary(
            "Then",
            f'{_locator_phrase(action)} should be / contain "{expected}"',
        )
    if kind == "scroll":
        return StepSummary("When", f"the user scrolls to {_locator_phrase(action)}")
    return StepSummary("When", f"the user performs {name or 'a step'}")


def summarise(actions: Sequence[Dict[str, Any]]) -> List[StepSummary]:
    if not isinstance(actions, (list, tuple)):
        raise SelfDescribeError("actions must be a sequence")
    if not actions:
        raise SelfDescribeError("actions must be non-empty")
    out: List[StepSummary] = []
    for i, action in enumerate(actions):
        if not isinstance(action, dict):
            raise SelfDescribeError(f"action #{i} is not a dict")
        out.append(_sentence_for(action))
    return out


def describe(actions: Sequence[Dict[str, Any]], title: str = "") -> str:
    """Render Gherkin-style paragraph with optional title heading."""
    summaries = summarise(actions)
    lines: List[str] = []
    if title:
        if not isinstance(title, str):
            raise SelfDescribeError("title must be string")
        lines.append(f"# {title}")
    last_phase = None
    for s in summaries:
        if s.phase == last_phase:
            lines.append(f"  And {s.sentence}")
        else:
            lines.append(f"  {s.phase} {s.sentence}")
            last_phase = s.phase
    return "\n".join(lines)


def assert_mentions(description: str, *needles: str) -> None:
    if not isinstance(description, str):
        raise SelfDescribeError("description must be string")
    if not needles:
        raise SelfDescribeError("must pass at least one needle")
    missing = [n for n in needles if n not in description]
    if missing:
        raise SelfDescribeError(
            f"description missing expected phrases: {missing}"
        )
