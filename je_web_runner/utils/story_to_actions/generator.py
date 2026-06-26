"""
從使用者故事 / Figma frame metadata 產生 WR action JSON。
The "smart" bit (LLM call) is abstracted behind a :class:`StoryClient`
protocol so this module stays unit-testable without network. Real usage
plugs in a Claude / GPT / local model client; tests inject a stub that
returns canned responses.

The output goes through a strict validator before being returned, so a
hallucinated action name or malformed args is caught here — not by the
executor at runtime.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Sequence, Union

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class StoryToActionsError(WebRunnerException):
    """Raised on bad inputs, client failures, or invalid generated actions."""


# Actions we trust the LLM to emit. Anything else is rejected so we don't
# silently let in hallucinations.
ALLOWED_ACTIONS = frozenset({
    "WR_to_url",
    "WR_click_element",
    "WR_double_click_element",
    "WR_input_to_element",
    "WR_submit_element",
    "WR_clear_element",
    "WR_implicitly_wait",
    "WR_assert_element_text",
    "WR_assert_element_visible",
    "WR_comment",
})


_LOCATOR_BY = frozenset({
    "id", "name", "xpath", "link text", "partial link text",
    "tag name", "class name", "css selector",
})


# ---------- input model -------------------------------------------------

@dataclass
class FigmaHint:
    """One element extracted from a Figma frame (optional context for the LLM)."""

    name: str
    type: str  # 'button' | 'input' | 'text' | ...
    selector_hint: Optional[str] = None  # e.g. data-test-id from layer metadata
    text: Optional[str] = None


@dataclass
class StoryPrompt:
    """The user story + optional structured context."""

    story: str
    start_url: Optional[str] = None
    figma_hints: List[FigmaHint] = field(default_factory=list)
    style_notes: List[str] = field(default_factory=list)  # extra constraints

    def __post_init__(self) -> None:
        if not isinstance(self.story, str) or not self.story.strip():
            raise StoryToActionsError("story must be a non-empty string")


# ---------- client protocol --------------------------------------------

class StoryClient(Protocol):
    """LLM client interface. ``generate`` returns a JSON-string action list."""

    def generate(self, prompt_text: str) -> str: ...


# ---------- prompt construction ----------------------------------------

def build_prompt_text(prompt: StoryPrompt) -> str:
    """Render a deterministic prompt the LLM client will see verbatim."""
    parts: List[str] = []
    parts.append("# Task")
    parts.append(
        "Translate the user story below into a WebRunner action JSON list. "
        f"Allowed action names: {sorted(ALLOWED_ACTIONS)}. "
        f"Locator strategies: {sorted(_LOCATOR_BY)}. "
        "Return ONLY a JSON array of action dicts, no commentary."
    )
    parts.append("\n# Story\n" + prompt.story.strip())
    if prompt.start_url:
        parts.append("\n# Start URL\n" + prompt.start_url)
    if prompt.figma_hints:
        parts.append("\n# Figma element hints")
        for hint in prompt.figma_hints:
            line = f"- {hint.name} ({hint.type})"
            if hint.selector_hint:
                line += f" selector: {hint.selector_hint}"
            if hint.text:
                line += f" text: {hint.text!r}"
            parts.append(line)
    if prompt.style_notes:
        parts.append("\n# Style notes")
        for note in prompt.style_notes:
            parts.append(f"- {note}")
    return "\n".join(parts)


# ---------- generation --------------------------------------------------

# NOSONAR python:S5852 — input is a bounded LLM response (≤ context window)
_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(.+?)```", re.DOTALL)


def generate_actions(
    prompt: StoryPrompt,
    client: StoryClient,
) -> List[Dict[str, Any]]:
    """Build prompt → ask client → parse → validate. Returns the action list."""
    prompt_text = build_prompt_text(prompt)
    try:
        raw = client.generate(prompt_text)
    except Exception as error:
        raise StoryToActionsError(f"story client failed: {error!r}") from error
    if not isinstance(raw, str):
        raise StoryToActionsError(
            f"story client returned {type(raw).__name__}, want JSON string"
        )
    actions = _parse_json_response(raw)
    validate_actions(actions)
    # Apply the start_url policy: if user supplied one and the LLM didn't
    # open with WR_to_url, prepend it. Saves a round of corrections.
    if prompt.start_url and not _starts_with_navigate(actions, prompt.start_url):
        actions.insert(0, {"WR_to_url": [prompt.start_url]})
        web_runner_logger.info(
            f"story_to_actions: prepended WR_to_url with start_url {prompt.start_url!r}"
        )
    return actions


def _parse_json_response(raw: str) -> List[Dict[str, Any]]:
    text = raw.strip()
    match = _JSON_BLOCK_RE.search(text)
    if match:
        text = match.group(1).strip()
    try:
        loaded = json.loads(text)
    except ValueError as error:
        raise StoryToActionsError(
            f"client response was not valid JSON: {error}; first 120 chars: {raw[:120]!r}"
        ) from error
    if not isinstance(loaded, list):
        raise StoryToActionsError(
            f"client response must be a JSON list, got {type(loaded).__name__}"
        )
    return loaded


def _starts_with_navigate(actions: Sequence[Dict[str, Any]], url: str) -> bool:
    if not actions:
        return False
    first = actions[0]
    return isinstance(first, dict) and first.get("WR_to_url") == [url]


# ---------- validation --------------------------------------------------

def validate_actions(actions: Sequence[Any]) -> None:
    """Raise :class:`StoryToActionsError` on the first invalid entry."""
    if not isinstance(actions, list):
        raise StoryToActionsError(
            f"actions must be a list, got {type(actions).__name__}"
        )
    if not actions:
        raise StoryToActionsError("actions list is empty")
    for index, action in enumerate(actions):
        _validate_one(index, action)

def _validate_one(index: int, action: Any) -> None:  # NOSONAR S3776 — cohesive logic; planned refactor in follow-up PR
    if not isinstance(action, dict) or len(action) != 1:
        raise StoryToActionsError(
            f"action #{index} must be a single-key dict, got {action!r}"
        )
    name, args = next(iter(action.items()))
    if name not in ALLOWED_ACTIONS:
        raise StoryToActionsError(
            f"action #{index} uses disallowed name {name!r}; allowed: {sorted(ALLOWED_ACTIONS)}"
        )
    if not isinstance(args, list):
        raise StoryToActionsError(
            f"action #{index} ({name}) args must be a list, got {type(args).__name__}"
        )
    if name == "WR_to_url":
        if len(args) != 1 or not isinstance(args[0], str) or not args[0]:
            raise StoryToActionsError(f"action #{index} WR_to_url needs [url]")
    elif name == "WR_implicitly_wait":
        if len(args) != 1 or not isinstance(args[0], (int, float)) or args[0] < 0:
            raise StoryToActionsError(
                f"action #{index} WR_implicitly_wait needs [seconds>=0]"
            )
    elif name == "WR_comment":
        if len(args) != 1 or not isinstance(args[0], str):
            raise StoryToActionsError(f"action #{index} WR_comment needs [text]")
    else:
        _validate_locator_action(index, name, args)

def _validate_locator_action(index: int, name: str, args: list) -> None:  # NOSONAR S3776 — cohesive logic; planned refactor in follow-up PR
    if len(args) < 2:
        raise StoryToActionsError(
            f"action #{index} ({name}) needs at least [by, value]"
        )
    by, value = args[0], args[1]
    if by not in _LOCATOR_BY:
        raise StoryToActionsError(
            f"action #{index} ({name}) uses unknown locator {by!r}; "
            f"allowed: {sorted(_LOCATOR_BY)}"
        )
    if not isinstance(value, str) or not value:
        raise StoryToActionsError(
            f"action #{index} ({name}) locator value must be a non-empty string"
        )
    if name == "WR_input_to_element":
        if len(args) != 3 or not isinstance(args[2], str):
            raise StoryToActionsError(
                f"action #{index} WR_input_to_element needs [by, value, text]"
            )
    elif name == "WR_assert_element_text":
        if len(args) != 3 or not isinstance(args[2], str):
            raise StoryToActionsError(
                f"action #{index} {name} needs [by, value, expected_text]"
            )
    elif name in (
        "WR_assert_element_visible",
        "WR_click_element", "WR_double_click_element",
        "WR_submit_element", "WR_clear_element",
    ) and len(args) != 2:
        raise StoryToActionsError(
            f"action #{index} {name} needs exactly [by, value]"
        )


# ---------- output helpers ----------------------------------------------

def write_actions_json(
    actions: Sequence[Dict[str, Any]],
    output_path: Union[str, Path],
) -> Path:
    """Persist validated actions to disk in WebRunner action JSON format."""
    validate_actions(actions)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(list(actions), fp, ensure_ascii=False, indent=2)
    return path
