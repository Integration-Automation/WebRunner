"""
WebRunner MCP server：用 Model Context Protocol (JSON-RPC 2.0) 把 WR_* 動作對外開放。
WebRunner MCP server. Exposes a curated subset of WebRunner actions and
helper utilities as MCP tools so any MCP-compatible client (Claude, IDE
plugins, etc.) can drive WebRunner.

Transport: ndjson over stdio (one JSON object per line). Run via::

    python -m je_web_runner.mcp_server

Supported methods: ``initialize``, ``tools/list``, ``tools/call``,
``resources/list``, ``ping``, ``shutdown``.
"""
from __future__ import annotations

import json
import sys
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, TextIO

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class McpServerError(WebRunnerException):
    """Raised when the server encounters a fatal protocol error."""


_MCP_PROTOCOL_VERSION = "2024-11-05"
_SERVER_NAME = "webrunner-mcp"
_SERVER_VERSION = "0.1.0"


@dataclass
class Tool:
    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: Callable[[Dict[str, Any]], Any]

    def schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


@dataclass
class McpServer:
    """JSON-RPC 2.0 server that speaks the MCP wire protocol over stdio."""

    tools: Dict[str, Tool] = field(default_factory=dict)
    initialized: bool = False

    def register(self, tool: Tool) -> None:
        if tool.name in self.tools:
            raise McpServerError(f"tool {tool.name!r} already registered")
        self.tools[tool.name] = tool

    def handle(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        request_id = message.get("id")
        method = message.get("method")
        params = message.get("params") or {}
        if not isinstance(method, str):
            return self._error(request_id, -32600, "method must be a string")
        try:
            if method == "initialize":
                result = self._initialize(params)
            elif method == "tools/list":
                result = self._tools_list()
            elif method == "tools/call":
                result = self._tools_call(params)
            elif method == "resources/list":
                result = {"resources": []}
            elif method == "ping":
                result = {}
            elif method == "shutdown":
                result = {}
            elif method == "notifications/initialized":
                self.initialized = True
                return None
            else:
                return self._error(request_id, -32601, f"unknown method {method!r}")
        except McpServerError as error:
            return self._error(request_id, -32000, str(error))
        except Exception as error:  # pylint: disable=broad-except
            web_runner_logger.error(
                f"mcp handler crashed in {method!r}: {error!r}\n{traceback.format_exc()}"
            )
            return self._error(request_id, -32000, f"handler error: {error!r}")
        if request_id is None:
            return None
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    def _initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        client_version = params.get("protocolVersion")
        web_runner_logger.info(f"mcp initialize from clientProtocol={client_version!r}")
        return {
            "protocolVersion": _MCP_PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}, "resources": {}},
            "serverInfo": {"name": _SERVER_NAME, "version": _SERVER_VERSION},
        }

    def _tools_list(self) -> Dict[str, Any]:
        return {"tools": [tool.schema() for tool in self.tools.values()]}

    def _tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if not isinstance(name, str):
            raise McpServerError("tool 'name' is required")
        if name not in self.tools:
            raise McpServerError(f"unknown tool {name!r}")
        if not isinstance(arguments, dict):
            raise McpServerError("'arguments' must be an object")
        try:
            result = self.tools[name].handler(arguments)
        except WebRunnerException as error:
            return {
                "content": [{"type": "text", "text": f"WebRunnerException: {error}"}],
                "isError": True,
            }
        rendered = result if isinstance(result, str) else json.dumps(
            result, ensure_ascii=False, default=str
        )
        return {"content": [{"type": "text", "text": rendered}], "isError": False}

    @staticmethod
    def _error(request_id: Any, code: int, message: str) -> Dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": code, "message": message},
        }


# --------------------------------------------------------------------------
# Default tool registry — wired to the existing WebRunner modules
# --------------------------------------------------------------------------

def _tool_lint_action(arguments: Dict[str, Any]) -> Any:
    from je_web_runner.utils.linter.action_linter import lint_action
    actions = arguments.get("actions")
    if not isinstance(actions, list):
        raise McpServerError("'actions' must be a list")
    return [{"index": f.index, "level": f.level, "message": f.message,
             "rule": f.rule} for f in lint_action(actions)]


def _tool_locator_strength(arguments: Dict[str, Any]) -> Any:
    from je_web_runner.utils.linter.locator_strength import score_locator
    score = score_locator(
        str(arguments.get("strategy", "")),
        str(arguments.get("value", "")),
    )
    return {
        "strategy": score.strategy,
        "value": score.value,
        "score": score.score,
        "reasons": score.reasons,
    }


def _tool_render_template(arguments: Dict[str, Any]) -> Any:
    from je_web_runner.utils.action_templates.templates import render_template
    return render_template(
        str(arguments.get("template", "")),
        arguments.get("parameters") or {},
    )


def _tool_compute_trend(arguments: Dict[str, Any]) -> Any:
    from je_web_runner.utils.trend_dashboard.trend import compute_trend
    return compute_trend(str(arguments.get("ledger_path", "")))


def _tool_validate_response(arguments: Dict[str, Any]) -> Any:
    from je_web_runner.utils.contract_testing.contract import validate_response
    body = arguments.get("body")
    schema = arguments.get("schema")
    if not isinstance(schema, dict):
        raise McpServerError("'schema' must be an object")
    result = validate_response(body, schema)
    return {"valid": result.valid, "errors": result.errors}


def _tool_summary_markdown(arguments: Dict[str, Any]) -> Any:
    from je_web_runner.utils.pr_comment.poster import (
        PrSummary,
        build_summary_markdown,
    )
    summary = PrSummary(
        total=int(arguments.get("total", 0)),
        passed=int(arguments.get("passed", 0)),
        failed=int(arguments.get("failed", 0)),
        skipped=int(arguments.get("skipped", 0)),
        flaky=int(arguments.get("flaky", 0)),
        duration_seconds=arguments.get("duration_seconds"),
    )
    return build_summary_markdown(summary, run_url=arguments.get("run_url"))


def _tool_diff_shard(arguments: Dict[str, Any]) -> Any:
    from je_web_runner.utils.sharding.diff_shard import select_action_files
    candidates = arguments.get("candidates") or []
    changed = arguments.get("changed") or []
    return select_action_files(list(candidates), list(changed))


def _tool_render_k8s(arguments: Dict[str, Any]) -> Any:
    from je_web_runner.utils.k8s_runner.manifest import (
        ShardJobConfig,
        render_job_manifests,
    )
    config = ShardJobConfig(
        name_prefix=str(arguments.get("name_prefix", "webrunner")),
        image=str(arguments.get("image", "")),
        total_shards=int(arguments.get("total_shards", 1)),
        actions_dir=str(arguments.get("actions_dir", "")),
    )
    return render_job_manifests(config)


def _tool_partition(arguments: Dict[str, Any]) -> Any:
    from je_web_runner.utils.sharding.shard import partition
    return partition(
        list(arguments.get("paths") or []),
        int(arguments.get("index", 1)),
        int(arguments.get("total", 1)),
    )


def build_default_tools() -> List[Tool]:
    """Construct the default tool list shipped with the server."""
    return [
        Tool(
            name="webrunner_lint_action",
            description="Lint a WebRunner action JSON list and report issues.",
            input_schema={
                "type": "object",
                "properties": {"actions": {"type": "array"}},
                "required": ["actions"],
            },
            handler=_tool_lint_action,
        ),
        Tool(
            name="webrunner_locator_strength",
            description="Score a (strategy, value) locator on a 0-100 scale.",
            input_schema={
                "type": "object",
                "properties": {
                    "strategy": {"type": "string"},
                    "value": {"type": "string"},
                },
                "required": ["strategy", "value"],
            },
            handler=_tool_locator_strength,
        ),
        Tool(
            name="webrunner_render_template",
            description="Render a built-in or registered action template.",
            input_schema={
                "type": "object",
                "properties": {
                    "template": {"type": "string"},
                    "parameters": {"type": "object"},
                },
                "required": ["template"],
            },
            handler=_tool_render_template,
        ),
        Tool(
            name="webrunner_compute_trend",
            description="Compute pass-rate / duration trend from a ledger file.",
            input_schema={
                "type": "object",
                "properties": {"ledger_path": {"type": "string"}},
                "required": ["ledger_path"],
            },
            handler=_tool_compute_trend,
        ),
        Tool(
            name="webrunner_validate_response",
            description="Validate a JSON value against a minimal JSON-Schema.",
            input_schema={
                "type": "object",
                "properties": {"body": {}, "schema": {"type": "object"}},
                "required": ["schema"],
            },
            handler=_tool_validate_response,
        ),
        Tool(
            name="webrunner_summary_markdown",
            description="Build a WebRunner PR summary in Markdown.",
            input_schema={
                "type": "object",
                "properties": {
                    "total": {"type": "integer"},
                    "passed": {"type": "integer"},
                    "failed": {"type": "integer"},
                    "skipped": {"type": "integer"},
                    "flaky": {"type": "integer"},
                    "duration_seconds": {"type": "number"},
                    "run_url": {"type": "string"},
                },
                "required": ["total", "passed", "failed"],
            },
            handler=_tool_summary_markdown,
        ),
        Tool(
            name="webrunner_diff_shard",
            description="Pick changed action files from a candidate / changed list.",
            input_schema={
                "type": "object",
                "properties": {
                    "candidates": {"type": "array", "items": {"type": "string"}},
                    "changed": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["candidates", "changed"],
            },
            handler=_tool_diff_shard,
        ),
        Tool(
            name="webrunner_render_k8s",
            description="Render Kubernetes Job manifests for shard parallelism.",
            input_schema={
                "type": "object",
                "properties": {
                    "name_prefix": {"type": "string"},
                    "image": {"type": "string"},
                    "total_shards": {"type": "integer"},
                    "actions_dir": {"type": "string"},
                },
                "required": ["name_prefix", "image", "total_shards", "actions_dir"],
            },
            handler=_tool_render_k8s,
        ),
        Tool(
            name="webrunner_partition_shard",
            description="Deterministic file partitioning for shard runs (SHA-1 mod N).",
            input_schema={
                "type": "object",
                "properties": {
                    "paths": {"type": "array", "items": {"type": "string"}},
                    "index": {"type": "integer"},
                    "total": {"type": "integer"},
                },
                "required": ["paths", "index", "total"],
            },
            handler=_tool_partition,
        ),
    ]


def make_default_server() -> McpServer:
    server = McpServer()
    for tool in build_default_tools():
        server.register(tool)
    return server


def serve_stdio(
    stdin: Optional[TextIO] = None,
    stdout: Optional[TextIO] = None,
    server: Optional[McpServer] = None,
) -> None:
    """
    主迴圈：每行一個 JSON-RPC 2.0 訊息，直到 stdin EOF
    Read newline-delimited JSON-RPC messages from ``stdin`` until EOF and
    write responses to ``stdout``.
    """
    in_stream = stdin or sys.stdin
    out_stream = stdout or sys.stdout
    used_server = server or make_default_server()
    for line in in_stream:
        stripped = line.strip()
        if not stripped:
            continue
        message = _parse_message(stripped, used_server, out_stream)
        if message is None:
            continue
        _dispatch(message, used_server, out_stream)


def _parse_message(line: str, server: McpServer, out_stream: TextIO) -> Any:
    try:
        return json.loads(line)
    except ValueError:
        response = server._error(  # pylint: disable=protected-access
            None, -32700, "parse error"
        )
        _write_message(out_stream, response)
        return None


def _dispatch(message: Any, server: McpServer, out_stream: TextIO) -> None:
    if isinstance(message, list):
        for item in message:
            _dispatch(item, server, out_stream)
        return
    if not isinstance(message, dict):
        return
    response = server.handle(message)
    if response is not None:
        _write_message(out_stream, response)


def _write_message(out_stream: TextIO, message: Dict[str, Any]) -> None:
    out_stream.write(json.dumps(message, ensure_ascii=False) + "\n")
    out_stream.flush()
