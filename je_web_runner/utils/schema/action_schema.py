"""
Action JSON Schema 匯出：給 IDE 做語法高亮 / 自動補完。
JSON Schema export for action JSON files. Pulls every registered
``WR_*`` command name from the executor and emits a Draft 2020-12 schema
that IDEs can use to validate and autocomplete.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class SchemaExportError(WebRunnerException):
    """Raised when a target path cannot be written."""


def _command_names() -> List[str]:
    """Pull every registered command name from the executor singleton."""
    # Imported lazily to avoid an import cycle with the executor module.
    from je_web_runner.utils.executor.action_executor import executor
    return sorted(name for name in executor.event_dict.keys() if name.startswith("WR_"))


def build_action_schema() -> Dict[str, Any]:
    """
    產生一份描述 action JSON 結構的 Draft 2020-12 Schema
    Build a Draft 2020-12 JSON Schema describing the action JSON format.

    The first slot of every action is constrained to the enum of registered
    command names; subsequent slots are loose (object or array) so the
    schema doesn't over-fit specific command signatures.
    """
    web_runner_logger.info("build_action_schema")
    command_enum = _command_names()
    action_schema: Dict[str, Any] = {
        "type": "array",
        "minItems": 1,
        "maxItems": 3,
        "prefixItems": [
            {"type": "string", "enum": command_enum, "title": "WebRunner command"},
            {"oneOf": [{"type": "object"}, {"type": "array"}]},
            {"type": "object"},
        ],
        "items": False,
    }
    list_form = {
        "type": "array",
        "items": {"$ref": "#/definitions/action"},
    }
    dict_form = {
        "type": "object",
        "properties": {
            "webdriver_wrapper": list_form,
            "meta": {
                "type": "object",
                "properties": {
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "depends_on": {"type": "array", "items": {"type": "string"}},
                },
                "additionalProperties": True,
            },
        },
        "required": ["webdriver_wrapper"],
        "additionalProperties": True,
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "WebRunner action JSON",
        "description": "Generated from the runtime executor event_dict.",
        "definitions": {"action": action_schema},
        "oneOf": [list_form, dict_form],
    }


def export_schema(path: str) -> str:
    """
    將 Schema 寫到 ``path`` 並回傳寫出的路徑
    Write the schema to ``path`` and return the resolved path.
    """
    web_runner_logger.info(f"export_schema: {path}")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.write_text(
            json.dumps(build_action_schema(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as error:
        raise SchemaExportError(f"failed to write schema: {error}") from error
    return str(target.resolve())
