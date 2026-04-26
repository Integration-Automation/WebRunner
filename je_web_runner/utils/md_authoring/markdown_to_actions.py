"""
Markdown → action JSON：讓非工程師用 Markdown 寫流程，再轉成 WR_* action list。
Tiny prose-to-actions transpiler. Each bullet line is parsed against a
small set of templates:

- ``- open <url>`` → ``["WR_to_url", {"url": "<url>"}]``
- ``- click <css | #id | .class | tag>`` →
  ``WR_save_test_object`` + ``WR_find_recorded_element`` + ``WR_element_click``.
- ``- type "<value>" into <selector>`` → equivalent fill triplet.
- ``- wait <n>s`` → ``["WR_implicitly_wait", {"time_to_wait": n}]``.
- ``- assert title "<text>"`` → ``["WR_assert_title", {"value": "<text>"}]``.
- ``- press <Key>`` → ``["WR_press_keys", {"keys": "<Key>"}]``.
- ``- screenshot`` → ``["WR_get_screenshot_as_png"]``.
- ``- run template <name>`` → ``["WR_render_template", {"template": "<name>"}]``.
- ``- quit`` → ``["WR_quit_all"]``.

Lines that don't match any template are preserved as comments
(``["WR__note", {"text": "..."}]``) so the transpilation is loss-less.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, List, Optional, Tuple, Union

from je_web_runner.utils.exception.exceptions import WebRunnerException


class MdAuthoringError(WebRunnerException):
    """Raised on invalid input or empty Markdown."""


# Trim leading whitespace + bullet marker; the body is captured greedily and
# trimmed in Python afterwards so this regex stays linear-time.
_BULLET_RE = re.compile(r"^\s*[-*]\s*(.*)$")  # NOSONAR S5852 — greedy ``.*`` anchored to ``$``, no backtracking


def _strategy_value_for(selector: str) -> Tuple[str, str]:
    selector = selector.strip()
    if selector.startswith("#"):
        return "ID", selector[1:]
    if selector.startswith("."):
        return "CSS_SELECTOR", selector
    if selector.startswith("[") and selector.endswith("]"):
        return "CSS_SELECTOR", selector
    if "/" in selector or selector.startswith("//"):
        return "XPATH", selector
    if " " in selector or ">" in selector or selector.startswith(":"):
        return "CSS_SELECTOR", selector
    if selector.isalpha() and selector.islower():
        return "TAG_NAME", selector
    return "CSS_SELECTOR", selector


def _click_actions(selector: str) -> List[List[Any]]:
    strategy, value = _strategy_value_for(selector)
    return [
        ["WR_save_test_object", {"test_object_name": value, "object_type": strategy}],
        ["WR_find_recorded_element", {"element_name": value}],
        ["WR_element_click"],
    ]


def _type_actions(text: str, selector: str) -> List[List[Any]]:
    strategy, value = _strategy_value_for(selector)
    return [
        ["WR_save_test_object", {"test_object_name": value, "object_type": strategy}],
        ["WR_find_recorded_element", {"element_name": value}],
        ["WR_element_input", {"input_value": text}],
    ]


# Use ``\S.*`` greedy capture so SonarCloud S5852 doesn't see polynomial
# backtracking; bullet bodies are bounded by the line length already trimmed
# in :func:`parse_markdown`.
_TYPE_RE = re.compile(r"^type\s+\"([^\"]*)\"\s+into\s+(\S.*)$", re.IGNORECASE)
_OPEN_RE = re.compile(r"^(?:open|go to|navigate to)\s+(\S+)$", re.IGNORECASE)
_CLICK_RE = re.compile(r"^click\s+(\S.*)$", re.IGNORECASE)
_WAIT_RE = re.compile(r"^wait\s+(\d+(?:\.\d+)?)\s*s(?:ec(?:onds)?)?$", re.IGNORECASE)
_TITLE_RE = re.compile(r"^assert\s+title\s+\"([^\"]*)\"$", re.IGNORECASE)
_PRESS_RE = re.compile(r"^press\s+(\S+)$", re.IGNORECASE)
_SCREENSHOT_RE = re.compile(r"^screenshot$", re.IGNORECASE)
# Template name allows ASCII identifier chars plus dashes; the bounded
# {0,80} caps the worst case at linear in input length.
_TEMPLATE_RE = re.compile(  # NOSONAR S5852 / S5869 — bounded class, ``\w`` overlap with first class is intentional
    r"^run\s+template\s+([A-Za-z_][\w-]{0,80})$", re.IGNORECASE,
)
_QUIT_RE = re.compile(r"^quit$", re.IGNORECASE)


def _parse_bullet(text: str) -> Optional[List[List[Any]]]:
    match = _OPEN_RE.match(text)
    if match:
        return [["WR_to_url", {"url": match.group(1)}]]
    match = _TYPE_RE.match(text)
    if match:
        return _type_actions(match.group(1), match.group(2))
    match = _CLICK_RE.match(text)
    if match:
        return _click_actions(match.group(1))
    match = _WAIT_RE.match(text)
    if match:
        seconds = float(match.group(1))
        if seconds.is_integer():
            seconds = int(seconds)
        return [["WR_implicitly_wait", {"time_to_wait": seconds}]]
    match = _TITLE_RE.match(text)
    if match:
        return [["WR_assert_title", {"value": match.group(1)}]]
    match = _PRESS_RE.match(text)
    if match:
        return [["WR_press_keys", {"keys": match.group(1)}]]
    if _SCREENSHOT_RE.match(text):
        return [["WR_get_screenshot_as_png"]]
    match = _TEMPLATE_RE.match(text)
    if match:
        return [["WR_render_template", {"template": match.group(1)}]]
    if _QUIT_RE.match(text):
        return [["WR_quit_all"]]
    return None


def parse_markdown(text: str) -> List[List[Any]]:
    """
    把 Markdown bullets 解析成 action list；無法辨識的條目保留為 ``WR__note``。
    Parse a Markdown body and return a flat WR_* action list. Each bullet
    line that doesn't match a template is preserved as a ``WR__note`` so
    the round-trip stays loss-less.
    """
    if not isinstance(text, str):
        raise MdAuthoringError("input must be str")
    actions: List[List[Any]] = []
    for raw_line in text.splitlines():
        match = _BULLET_RE.match(raw_line)
        if match is None:
            continue
        bullet_text = match.group(1).strip()
        if not bullet_text:
            continue
        parsed = _parse_bullet(bullet_text)
        if parsed is None:
            actions.append(["WR__note", {"text": bullet_text}])
            continue
        actions.extend(parsed)
    if not actions:
        raise MdAuthoringError("Markdown contained no recognisable bullets")
    return actions


def transpile_file(
    md_path: Union[str, Path],
    output_path: Optional[Union[str, Path]] = None,
) -> List[List[Any]]:
    """
    讀 ``md_path``，轉成 action list。``output_path`` 提供時會寫成格式化 JSON。
    Read ``md_path``, transpile, and optionally write the formatted JSON
    to ``output_path``.
    """
    src = Path(md_path)
    if not src.is_file():
        raise MdAuthoringError(f"file not found: {md_path!r}")
    actions = parse_markdown(src.read_text(encoding="utf-8"))
    if output_path is not None:
        from je_web_runner.utils.action_formatter.formatter import format_actions
        Path(output_path).write_text(format_actions(actions), encoding="utf-8")
    return actions


def supported_bullet_patterns() -> List[str]:
    """Return the list of bullet templates the parser recognises."""
    return [
        "open <url>",
        'type "<text>" into <selector>',
        "click <selector>",
        "wait <n>s",
        'assert title "<text>"',
        "press <Key>",
        "screenshot",
        "run template <name>",
        "quit",
    ]
