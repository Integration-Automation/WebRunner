"""
Action JSON formatter：把 action 列表寫成 canonical 形式（鍵順序、縮排穩定）。
Deterministic formatter for WebRunner action JSON files. Each action is
emitted on a single line with kwargs in a canonical order so diffs are
small and grep-friendly:

- recognised kwargs (``url`` / ``test_object_name`` / ``object_type`` /
  ``element_name`` / ``input_value`` / ``timeout`` / ``time_to_wait`` /
  ``key`` / ``keys`` / ``script`` / ``args``) are emitted first in that
  order;
- everything else follows alphabetised.

The output preserves the underlying meaning byte-for-byte (no rounding,
no string normalisation other than UTF-8 encoding).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union

from je_web_runner.utils.exception.exceptions import WebRunnerException


class ActionFormatterError(WebRunnerException):
    """Raised when input cannot be parsed as an action list."""


_PREFERRED_KWARGS_ORDER = (
    "url",
    "test_object_name",
    "object_type",
    "element_name",
    "input_value",
    "timeout",
    "time_to_wait",
    "key",
    "keys",
    "script",
    "args",
)


def _sorted_kwargs(kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """Return kwargs with the canonical key order applied."""
    if not isinstance(kwargs, dict):
        raise ActionFormatterError("action kwargs must be a dict")
    preferred_present = [k for k in _PREFERRED_KWARGS_ORDER if k in kwargs]
    rest = sorted(k for k in kwargs.keys() if k not in _PREFERRED_KWARGS_ORDER)
    ordered: Dict[str, Any] = {}
    for key in preferred_present + rest:
        value = kwargs[key]
        ordered[key] = _canonicalise(value)
    return ordered


def _canonicalise(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _canonicalise(value[k]) for k in sorted(value.keys())}
    if isinstance(value, list):
        return [_canonicalise(item) for item in value]
    return value


def _format_action_line(action: List[Any]) -> str:
    if not isinstance(action, list) or not action:
        raise ActionFormatterError(f"action must be a non-empty list: {action!r}")
    command = action[0]
    if not isinstance(command, str):
        raise ActionFormatterError(f"action[0] (command) must be str: {command!r}")
    if len(action) == 1:
        return json.dumps([command], ensure_ascii=False)
    if len(action) == 2:
        body = action[1]
        if isinstance(body, dict):
            return json.dumps([command, _sorted_kwargs(body)], ensure_ascii=False)
        if isinstance(body, list):
            return json.dumps([command, [_canonicalise(x) for x in body]],
                              ensure_ascii=False)
        raise ActionFormatterError(
            f"action[1] must be dict or list, got {type(body).__name__}"
        )
    if len(action) == 3:
        positional = action[1]
        kwargs = action[2]
        if not isinstance(positional, list):
            raise ActionFormatterError(
                "length-3 action[1] must be a list of positional args"
            )
        if not isinstance(kwargs, dict):
            raise ActionFormatterError(
                "length-3 action[2] must be a dict of kwargs"
            )
        return json.dumps(
            [command, [_canonicalise(x) for x in positional], _sorted_kwargs(kwargs)],
            ensure_ascii=False,
        )
    raise ActionFormatterError(
        f"action length must be 1/2/3, got {len(action)}"
    )


def format_actions(actions: List[Any], indent: int = 2) -> str:
    """
    把 action list 轉成 canonical 多行 JSON。``indent`` 為頂層 array 縮排空白數。
    Format an action list as canonical JSON. Each action lives on its own
    line; the surrounding array uses ``indent`` spaces.
    """
    if not isinstance(actions, list):
        raise ActionFormatterError("actions must be a list")
    if indent < 0:
        raise ActionFormatterError("indent must be >= 0")
    if not actions:
        return "[]\n"
    pad = " " * indent
    lines = [pad + _format_action_line(action) for action in actions]
    return "[\n" + ",\n".join(lines) + "\n]\n"


def format_text(text: str, indent: int = 2) -> str:
    """Parse JSON text and return its formatted form."""
    try:
        actions = json.loads(text)
    except ValueError as error:
        raise ActionFormatterError(f"input is not valid JSON: {error}") from error
    return format_actions(actions, indent=indent)


def format_file(path: Union[str, Path], write: bool = True,
                indent: int = 2) -> Tuple[str, bool]:
    """
    讀檔、格式化、（可選）寫回；回傳 ``(formatted_text, changed)``。
    Reformat ``path``. When ``write`` is True the file is rewritten only
    if its content changed. Returns the new text and whether it was
    different from the original.
    """
    target = Path(path)
    if not target.is_file():
        raise ActionFormatterError(f"file not found: {path!r}")
    original = target.read_text(encoding="utf-8")
    formatted = format_text(original, indent=indent)
    changed = formatted != original
    if write and changed:
        target.write_text(formatted, encoding="utf-8")
    return formatted, changed
