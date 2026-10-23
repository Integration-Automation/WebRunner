"""Portable JSON Schema for local agent task files and MCP clients."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from je_web_runner.utils.agent.planners import ACTION_SCHEMA


def build_agent_schema() -> dict[str, Any]:
    """Describe TaskSpec JSON; runtime validation also checks action-specific requirements."""
    strings = {name: {"type": "string"} for name in ("value", "selector", "key", "frame")}
    condition = {"type": "object", "properties": {
        "kind": {"enum": ["url_contains", "text_contains", "visible", "extracted_equals"]}, **strings,
    }, "required": ["kind"], "additionalProperties": False}
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema", "title": "WebRunner local agent task",
        "type": "object", "additionalProperties": False,
        "required": ["goal", "start_url", "success"],
        "properties": {
            "goal": {"type": "string", "minLength": 1},
            "start_url": {"type": "string", "pattern": "^https?://"},
            "backend": {"enum": ["selenium", "playwright"], "default": "selenium"},
            "planner": {"enum": ["steps", "ollama"], "default": "steps"},
            "model": {"type": "string", "description": "Explicitly installed local open-source model name."},
            "success": {"type": "array", "minItems": 1, "items": condition},
            "steps": {"type": "array", "items": ACTION_SCHEMA},
            "extract": {"type": "object", "additionalProperties": {"type": "string", "minLength": 1}},
            "allowed_env": {"type": "array", "items": {"type": "string", "pattern": "^[A-Za-z_][A-Za-z0-9_]*$"}},
            "max_steps": {"type": "integer", "minimum": 1, "default": 25},
            "timeout": {"type": "number", "exclusiveMinimum": 0, "default": 300},
            "action_timeout": {"type": "number", "exclusiveMinimum": 0, "default": 15},
            "headless": {"type": "boolean", "default": True},
        },
    }


def export_agent_schema(path: str | Path) -> str:
    """Export the task schema as UTF-8 JSON."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(build_agent_schema(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return str(target.resolve())
