"""
WebRunner MCP server：用 Model Context Protocol (JSON-RPC 2.0) 把 WR_* 動作對外開放。
WebRunner MCP server. Exposes a curated subset of WebRunner actions and
helper utilities as MCP tools so any MCP-compatible client (Claude, IDE
plugins, etc.) can drive WebRunner.

Transport: ndjson over stdio (one JSON object per line). Run via::

    python -m je_web_runner.mcp_server

Supported methods: ``initialize``, ``notifications/initialized``,
``tools/list``, ``tools/call`` and ``ping``. ``initialize`` answers with the
client's protocol version when it is one of :data:`SUPPORTED_PROTOCOL_VERSIONS`,
otherwise with the newest.
"""
from __future__ import annotations

import json
import os
import sys
import traceback
from importlib import metadata
from dataclasses import dataclass, field
from typing import Any, Callable, TextIO

from je_web_runner.mcp_server._types import McpInvalidParams, McpServerError, Tool, ToolResult
from je_web_runner.mcp_server.offline_tools import build_default_tools
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


#: Every revision with the ``initialize`` handshake this server speaks, newest first.
#: The server offers tools only, so the later revisions' optional features (resources,
#: prompts, elicitation, tasks) do not apply; it follows the rules they add for every
#: version: tool failures are ``isError`` results, notifications get no reply, batches
#: are rejected.
SUPPORTED_PROTOCOL_VERSIONS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")
_NEWEST_PROTOCOL_VERSION = SUPPORTED_PROTOCOL_VERSIONS[0]
#: The first revision whose ``Implementation`` carries ``description``.
_DESCRIPTION_SINCE = "2025-11-25"
_SERVER_DESCRIPTION = (
    "Browser automation with Selenium or Playwright: run WebRunner action lists, "
    "plus offline tools for authoring, linting and triaging them."
)
_INSTRUCTIONS = (
    "WebRunner drives a real browser through action lists of [command, params] entries. "
    "Call webrunner_list_commands to see the WR_* commands, then webrunner_run_actions to run them; "
    "the browser stays open between calls until an action list runs WR_quit (Selenium) or WR_pw_quit "
    "(Playwright). A result with isError true lists the failed actions under 'failed'. The other "
    "tools (lint, format, translate, scan, shard...) work offline and never open a browser."
)

_SERVER_NAME = "webrunner-mcp"
_DISTRIBUTIONS = ("je_web_runner", "je_web_runner_dev")


def negotiate_protocol_version(requested: Any) -> str:
    """
    回覆 ``initialize`` 用的協定版本
    The version to answer ``initialize`` with: the client's when this server speaks it,
    otherwise the newest. An unsupported version is never echoed back, because the client
    would take it as agreed.
    """
    return requested if requested in SUPPORTED_PROTOCOL_VERSIONS else _NEWEST_PROTOCOL_VERSION


def server_version() -> str:
    """The installed package's version (stable or dev distribution), or ``0+unknown`` from a source tree."""
    for distribution in _DISTRIBUTIONS:
        try:
            return metadata.version(distribution)
        except metadata.PackageNotFoundError:
            continue
    return "0+unknown"


@dataclass
class McpServer:
    """JSON-RPC 2.0 server that speaks the MCP wire protocol over stdio."""

    tools: dict[str, Tool] = field(default_factory=dict)
    initialized: bool = False

    def register(self, tool: Tool) -> None:
        if tool.name in self.tools:
            raise McpServerError(f"tool {tool.name!r} already registered")
        self.tools[tool.name] = tool

    def handle(self, message: dict[str, Any]) -> dict[str, Any] | None:
        """
        處理一則訊息；notification（沒有 ``id``）一律不回應
        Answer one JSON-RPC message. A notification (no ``id`` member) never gets a response,
        not even an error.
        """
        response = self._respond(message)
        if "id" not in message:
            return None
        return response

    def _respond(self, message: dict[str, Any]) -> dict[str, Any] | None:
        request_id = message.get("id")
        method = message.get("method")
        params = message.get("params") or {}
        if not isinstance(method, str):
            return self._error(request_id, -32600, "method must be a string")
        handlers: dict[str, Callable[[dict[str, Any]], Any]] = {
            "initialize": self._initialize,
            "tools/list": lambda _params: self._tools_list(),
            "tools/call": self._tools_call,
            "ping": lambda _params: {},
            "notifications/initialized": self._on_initialized,
        }
        handler = handlers.get(method)
        if handler is None:
            return self._error(request_id, -32601, f"unknown method {method!r}")
        try:
            result = handler(params)
        except McpInvalidParams as error:
            return self._error(request_id, -32602, str(error))
        except Exception as error:  # pylint: disable=broad-except — answered as -32603 and logged
            web_runner_logger.error(
                f"mcp handler crashed in {method!r}: {error!r}\n{traceback.format_exc()}"
            )
            return self._error(request_id, -32603, f"internal error: {error!r}")
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    def _on_initialized(self, _params: dict[str, Any]) -> None:
        self.initialized = True

    def _initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        client_version = params.get("protocolVersion")
        version = negotiate_protocol_version(client_version)
        web_runner_logger.info(f"mcp initialize: client {client_version!r}, answered {version!r}")
        server_info = {"name": _SERVER_NAME, "version": server_version()}
        if version >= _DESCRIPTION_SINCE:
            server_info["description"] = _SERVER_DESCRIPTION
        return {
            "protocolVersion": version,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": server_info,
            "instructions": _INSTRUCTIONS,
        }

    def _tools_list(self) -> dict[str, Any]:
        return {"tools": [tool.schema() for tool in self.tools.values()]}

    def _tools_call(self, params: dict[str, Any]) -> dict[str, Any]:
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if not isinstance(name, str):
            raise McpInvalidParams("tool 'name' is required")
        if name not in self.tools:
            raise McpInvalidParams(f"unknown tool {name!r}")
        if not isinstance(arguments, dict):
            raise McpInvalidParams("'arguments' must be an object")
        try:
            result = self.tools[name].handler(arguments)
        except Exception as error:  # pylint: disable=broad-except — a tool failure is a result, not a crash
            web_runner_logger.warning(
                f"mcp tool {name!r} failed: {error!r}\n{traceback.format_exc()}"
            )
            return _text_result(f"{type(error).__name__}: {error}", is_error=True)
        if isinstance(result, ToolResult):
            return _text_result(_render(result.value), is_error=result.is_error)
        return _text_result(_render(result), is_error=False)

    @staticmethod
    def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": code, "message": message},
        }


def _render(value: Any) -> str:
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)


def _text_result(text: str, *, is_error: bool) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


def make_default_server() -> McpServer:
    # Imported lazily so ``server`` can be imported without dragging the
    # full executor (and therefore Selenium / Playwright) into modules that
    # only need the protocol skeleton.
    from je_web_runner.mcp_server.browser_tools import build_browser_tools
    server = McpServer()
    for tool in build_default_tools():
        server.register(tool)
    for tool in build_browser_tools():
        server.register(tool)
    return server


def serve_stdio(
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    server: McpServer | None = None,
) -> None:
    """
    主迴圈：每行一個 JSON-RPC 2.0 訊息，直到 stdin EOF
    Read newline-delimited JSON-RPC messages from ``stdin`` until EOF and
    write responses to ``stdout``.

    With the default streams both directions are UTF-8 with ``\\n`` line ends whatever the
    console code page. Side effect of the default ``stdout``: for the rest of the process
    anything else written to stdout (``print``, C extensions, child processes) goes to
    stderr, so only protocol messages reach the client.
    """
    in_stream = stdin or open(  # noqa: SIM115 — wraps the process stdin; the OS closes it
        sys.stdin.fileno(), encoding="utf-8", closefd=False,
    )
    out_stream = stdout or _claim_stdout()
    used_server = server or make_default_server()
    for line in in_stream:
        stripped = line.strip()
        if not stripped:
            continue
        message = _parse_message(stripped, used_server, out_stream)
        if message is None:
            continue
        _dispatch(message, used_server, out_stream)


def _claim_stdout() -> TextIO:
    """Keep fd 1 for the protocol (UTF-8, LF) and point the process's stdout at stderr."""
    sys.stdout.flush()
    protocol_out = os.fdopen(os.dup(sys.stdout.fileno()), "w", encoding="utf-8", newline="\n")
    os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
    sys.stdout = sys.stderr
    return protocol_out


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
        # JSON-RPC batching was removed from MCP in revision 2025-06-18.
        _write_message(out_stream, server._error(  # pylint: disable=protected-access
            None, -32600, "batch requests are not supported"))
        return
    if not isinstance(message, dict):
        _write_message(out_stream, server._error(  # pylint: disable=protected-access
            None, -32600, "a message must be a JSON object"))
        return
    response = server.handle(message)
    if response is not None:
        _write_message(out_stream, response)


def _write_message(out_stream: TextIO, message: dict[str, Any]) -> None:
    out_stream.write(json.dumps(message, ensure_ascii=False) + "\n")
    out_stream.flush()
