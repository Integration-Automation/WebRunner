"""
依工具的 input schema 檢查參數 / Check tool arguments against the tool's input schema.

Covers the subset of JSON Schema the shipped tools use: ``type``, ``required``,
``properties``, ``additionalProperties: false`` and one level of ``items.type``.
Problems come back as messages, which the server returns as an ``isError`` result
so the model can correct its call (MCP 2025-11-25, SEP-1303).
"""
from __future__ import annotations

from typing import Any

_PYTHON_TYPES: dict[str, type | tuple[type, ...]] = {
    "object": dict, "array": list, "string": str, "boolean": bool,
}


def _matches(value: Any, expected: str) -> bool:
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    python_type = _PYTHON_TYPES.get(expected)
    return python_type is None or isinstance(value, python_type)


def _check_property(name: str, value: Any, spec: dict[str, Any]) -> list[str]:
    expected = spec.get("type")
    if isinstance(expected, str) and not _matches(value, expected):
        return [f"{name!r} must be of type {expected}"]
    item_type = (spec.get("items") or {}).get("type") if expected == "array" else None
    if isinstance(item_type, str) and not all(_matches(item, item_type) for item in value):
        return [f"every item of {name!r} must be of type {item_type}"]
    return []


def validate_arguments(schema: dict[str, Any], arguments: dict[str, Any]) -> list[str]:
    """
    回傳參數不符 schema 的地方；空清單代表通過
    Return what is wrong with ``arguments`` for ``schema``; an empty list means valid.
    ``None`` for an optional argument counts as leaving it out.
    """
    required = schema.get("required") or []
    problems = [f"missing required argument {name!r}" for name in required if name not in arguments]
    properties = schema.get("properties") or {}
    for name, value in arguments.items():
        spec = properties.get(name)
        if spec is None:
            if schema.get("additionalProperties") is False:
                problems.append(f"unknown argument {name!r}")
            continue
        if value is None and name not in required:
            continue
        problems.extend(_check_property(name, value, spec))
    return problems
