"""
MCP tools that drive a real browser via the WebRunner executor.

The executor already maps ~200 ``WR_*`` strings to callables (Selenium,
Playwright, reporting, …); these tools simply hand a JSON-RPC ``arguments``
payload through to ``execute_action`` / ``execute_files``.

Two hazards are handled here so the rest of the protocol stays clean:

* ``execute_action`` prints each record to stdout. The MCP server speaks
  JSON-RPC over stdout, so stray prints corrupt the wire. We redirect stdout
  into a buffer for the duration of the call and surface it as ``stdout`` in
  the result.
* Action return values may contain WebDriver / WebElement instances that
  ``json.dumps`` cannot serialise. ``_serialize_value`` reduces those to
  ``repr()`` strings before the server's encoder sees them.
"""
from __future__ import annotations

import io
from contextlib import redirect_stdout
from typing import Any, Dict, List

from je_web_runner.mcp_server.server import McpServerError, Tool


def _serialize_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_serialize_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _serialize_value(item) for key, item in value.items()}
    return repr(value)


def _serialize_record(record: Dict[Any, Any]) -> Dict[str, Any]:
    return {str(key): _serialize_value(value) for key, value in record.items()}


def _tool_run_actions(arguments: Dict[str, Any]) -> Any:
    from je_web_runner.utils.executor.action_executor import execute_action
    actions = arguments.get("actions")
    if not isinstance(actions, list):
        raise McpServerError("'actions' must be a list of [name, params] entries")
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        record = execute_action(actions)
    return {"stdout": buffer.getvalue(), "record": _serialize_record(record)}


def _tool_run_action_files(arguments: Dict[str, Any]) -> Any:
    from je_web_runner.utils.executor.action_executor import execute_files
    files = arguments.get("files")
    if not isinstance(files, list):
        raise McpServerError("'files' must be a list of file paths")
    if not all(isinstance(path, str) for path in files):
        raise McpServerError("each entry in 'files' must be a string path")
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        results = execute_files(files)
    return {
        "stdout": buffer.getvalue(),
        "records": [_serialize_record(record) for record in results],
    }


def _tool_list_commands(_arguments: Dict[str, Any]) -> Any:
    from je_web_runner.utils.executor.action_executor import executor
    return sorted(name for name in executor.event_dict if name.startswith("WR_"))


def build_browser_tools() -> List[Tool]:
    """Return the browser-execution MCP tools."""
    return [
        Tool(
            name="webrunner_run_actions",
            description=(
                "Execute a WebRunner action list against a real browser. Each"
                " entry is [command_name, params] where params is a dict of"
                " kwargs or a list of positional args. Common commands:"
                " WR_get_webdriver_manager, WR_to_url, WR_send_keys,"
                " WR_click_element, WR_pw_launch, WR_pw_to_url, WR_quit."
                " Returns {'stdout': str, 'record': {action_repr: result}}."
            ),
            input_schema={
                "type": "object",
                "properties": {"actions": {"type": "array"}},
                "required": ["actions"],
            },
            handler=_tool_run_actions,
        ),
        Tool(
            name="webrunner_run_action_files",
            description=(
                "Read one or more JSON action files from disk and execute"
                " them sequentially against a real browser. Returns"
                " {'stdout': str, 'records': [<per-file record>]}."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "files": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["files"],
            },
            handler=_tool_run_action_files,
        ),
        Tool(
            name="webrunner_list_commands",
            description=(
                "Return every WR_* command currently registered in the"
                " executor, so a caller can discover the action surface"
                " before composing webrunner_run_actions payloads."
            ),
            input_schema={"type": "object", "properties": {}},
            handler=_tool_list_commands,
        ),
    ]
