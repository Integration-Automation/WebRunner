"""
The generated command reference and action schema list exactly the registered commands.

Both are generated (architecture.md §5 step 5) and were once 41 commands behind. Only the
command names are compared: the signatures in the reference are formatted by ``inspect``,
which differs between the Python versions CI runs.
"""
import json
import re
from pathlib import Path

from je_web_runner.utils.executor.action_executor import executor

_REFERENCE_DIR = Path(__file__).resolve().parents[2] / "docs" / "reference"
_REGENERATE = (
    "regenerate with export_command_reference('docs/reference/command_reference.md') and "
    "export_schema('docs/reference/webrunner-action-schema.json')"
)


def _registered() -> set[str]:
    return {name for name in executor.event_dict if name.startswith("WR_")}


def _schema_enums(node) -> list[list[str]]:
    if isinstance(node, dict):
        found = [node["enum"]] if isinstance(node.get("enum"), list) else []
        for value in node.values():
            found.extend(_schema_enums(value))
        return found
    if isinstance(node, list):
        return [enum for item in node for enum in _schema_enums(item)]
    return []


def test_command_reference_lists_every_registered_command():
    text = (_REFERENCE_DIR / "command_reference.md").read_text(encoding="utf-8")
    listed = set(re.findall(r"^\| `(WR_\w+)` \|", text, re.MULTILINE))
    assert listed == _registered(), _REGENERATE  # nosec B101


def test_action_schema_enum_is_the_registered_commands():
    schema = json.loads((_REFERENCE_DIR / "webrunner-action-schema.json").read_text(encoding="utf-8"))
    command_enums = [set(enum) for enum in _schema_enums(schema) if any(str(v).startswith("WR_") for v in enum)]
    assert command_enums, "no command enum in the schema"  # nosec B101
    assert all(enum == _registered() for enum in command_enums), _REGENERATE  # nosec B101
