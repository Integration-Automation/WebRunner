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

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class McpServerError(WebRunnerException):
    """Raised when the server encounters a fatal protocol error."""


class McpInvalidParams(McpServerError):
    """A request's params are unusable (unknown tool, arguments not an object); JSON-RPC -32602."""


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

# Reused error messages — extracted so SonarCloud S1192 stays quiet and
# downstream tooling can grep for them.
_ERR_ACTIONS_LIST = "'actions' must be a list"
_ERR_TEXT_STRING = "'text' must be a string"
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
class Tool:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[[dict[str, Any]], Any]

    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


@dataclass
class ToolResult:
    """
    工具回傳值加上是否失敗（送出時成為 ``isError``）
    A handler's value plus whether it reports a failure, sent as the result's ``isError``.
    Handlers may also return a bare value (success) or raise (failure).
    """
    value: Any
    is_error: bool = False


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


# --------------------------------------------------------------------------
# Default tool registry — wired to the existing WebRunner modules
# --------------------------------------------------------------------------

def _tool_lint_action(arguments: dict[str, Any]) -> Any:
    from je_web_runner.utils.linter.action_linter import lint_action
    actions = arguments.get("actions")
    if not isinstance(actions, list):
        raise McpServerError(_ERR_ACTIONS_LIST)
    # ``lint_action`` returns ``List[Dict[str, Any]]`` with ``rule`` /
    # ``severity`` / ``message`` / ``location`` keys; pass through verbatim
    # so MCP clients see the same shape the Python API exposes.
    return list(lint_action(actions))


def _tool_locator_strength(arguments: dict[str, Any]) -> Any:
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


def _tool_render_template(arguments: dict[str, Any]) -> Any:
    from je_web_runner.utils.action_templates.templates import render_template
    return render_template(
        str(arguments.get("template", "")),
        arguments.get("parameters") or {},
    )


def _tool_compute_trend(arguments: dict[str, Any]) -> Any:
    from je_web_runner.utils.trend_dashboard.trend import compute_trend
    return compute_trend(str(arguments.get("ledger_path", "")))


def _tool_validate_response(arguments: dict[str, Any]) -> Any:
    from je_web_runner.utils.contract_testing.contract import validate_response
    body = arguments.get("body")
    schema = arguments.get("schema")
    if not isinstance(schema, dict):
        raise McpServerError("'schema' must be an object")
    result = validate_response(body, schema)
    return {"valid": result.valid, "errors": result.errors}


def _tool_summary_markdown(arguments: dict[str, Any]) -> Any:
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


def _tool_diff_shard(arguments: dict[str, Any]) -> Any:
    from je_web_runner.utils.sharding.diff_shard import select_action_files
    candidates = arguments.get("candidates") or []
    changed = arguments.get("changed") or []
    return select_action_files(list(candidates), list(changed))


def _tool_render_k8s(arguments: dict[str, Any]) -> Any:
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


def _tool_partition(arguments: dict[str, Any]) -> Any:
    from je_web_runner.utils.sharding.shard import partition
    return partition(
        list(arguments.get("paths") or []),
        int(arguments.get("index", 1)),
        int(arguments.get("total", 1)),
    )


def _tool_format_actions(arguments: dict[str, Any]) -> Any:
    from je_web_runner.utils.action_formatter.formatter import format_actions
    actions = arguments.get("actions")
    if not isinstance(actions, list):
        raise McpServerError(_ERR_ACTIONS_LIST)
    return format_actions(actions, indent=int(arguments.get("indent", 2)))


def _tool_parse_markdown(arguments: dict[str, Any]) -> Any:
    from je_web_runner.utils.md_authoring.markdown_to_actions import parse_markdown
    text = arguments.get("text")
    if not isinstance(text, str):
        raise McpServerError(_ERR_TEXT_STRING)
    return parse_markdown(text)


def _tool_translate_actions_to_playwright(arguments: dict[str, Any]) -> Any:
    from je_web_runner.utils.sel_to_pw.translator import translate_action_list
    actions = arguments.get("actions")
    if not isinstance(actions, list):
        raise McpServerError(_ERR_ACTIONS_LIST)
    return translate_action_list(actions)


def _tool_translate_python_to_playwright(arguments: dict[str, Any]) -> Any:
    from je_web_runner.utils.sel_to_pw.translator import translate_python_source
    source = arguments.get("source")
    if not isinstance(source, str):
        raise McpServerError("'source' must be a string")
    translations = translate_python_source(source)
    return [
        {"line": t.line, "original": t.original,
         "translated": t.translated, "note": t.note}
        for t in translations
    ]


def _tool_pom_from_html(arguments: dict[str, Any]) -> Any:
    from je_web_runner.utils.pom_codegen.codegen import (
        discover_elements_from_html,
        render_pom_module,
    )
    html = arguments.get("html")
    if not isinstance(html, str):
        raise McpServerError("'html' must be a string")
    elements = discover_elements_from_html(html)
    class_name = str(arguments.get("class_name", "WebRunnerPage"))
    return {
        "module": render_pom_module(elements, class_name=class_name),
        "elements": [
            {"name": e.name, "strategy": e.strategy,
             "value": e.value, "tag": e.tag, "source": e.source}
            for e in elements
        ],
    }


def _tool_scan_pii(arguments: dict[str, Any]) -> Any:
    from je_web_runner.utils.pii_scanner.scanner import scan_text
    text = arguments.get("text")
    if not isinstance(text, str):
        raise McpServerError(_ERR_TEXT_STRING)
    categories = arguments.get("categories")
    findings = scan_text(text, categories=categories)
    return [
        {"category": f.category, "start": f.start,
         "end": f.end, "redacted": f.redacted}
        for f in findings
    ]


def _tool_redact_pii(arguments: dict[str, Any]) -> Any:
    from je_web_runner.utils.pii_scanner.scanner import redact_text
    text = arguments.get("text")
    if not isinstance(text, str):
        raise McpServerError(_ERR_TEXT_STRING)
    return redact_text(
        text,
        replacement=str(arguments.get("replacement", "[REDACTED]")),
        categories=arguments.get("categories"),
    )


def _tool_cluster_failures(arguments: dict[str, Any]) -> Any:
    from je_web_runner.utils.failure_cluster.clustering import (
        cluster_failures,
        cluster_summary,
    )
    failures = arguments.get("failures")
    if not isinstance(failures, list):
        raise McpServerError("'failures' must be a list")
    top_n = arguments.get("top_n")
    if top_n is not None:
        top_n = int(top_n)
    clusters = cluster_failures(failures, top_n=top_n)
    return cluster_summary(clusters)


def _tool_a11y_diff(arguments: dict[str, Any]) -> Any:
    from je_web_runner.utils.accessibility.a11y_diff import diff_violations
    baseline = arguments.get("baseline")
    current = arguments.get("current")
    if not isinstance(baseline, list) or not isinstance(current, list):
        raise McpServerError("'baseline' and 'current' must be lists")
    diff = diff_violations(baseline, current)
    return {
        "added": diff.added,
        "resolved": diff.resolved,
        "persisting": diff.persisting,
        "regressed": diff.regressed,
    }


def _tool_score_action_locators(arguments: dict[str, Any]) -> Any:
    from je_web_runner.utils.linter.locator_strength import score_action_locators
    actions = arguments.get("actions")
    if not isinstance(actions, list):
        raise McpServerError(_ERR_ACTIONS_LIST)
    return list(score_action_locators(actions))


def build_default_tools() -> list[Tool]:
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
        Tool(
            name="webrunner_format_actions",
            description="Format an action JSON list with canonical kwarg order.",
            input_schema={
                "type": "object",
                "properties": {
                    "actions": {"type": "array"},
                    "indent": {"type": "integer"},
                },
                "required": ["actions"],
            },
            handler=_tool_format_actions,
        ),
        Tool(
            name="webrunner_parse_markdown",
            description="Transpile a Markdown bullet list into a WR_* action list.",
            input_schema={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
            handler=_tool_parse_markdown,
        ),
        Tool(
            name="webrunner_translate_actions_to_playwright",
            description=(
                "Rewrite a WR_* action list to its WR_pw_* Playwright"
                " equivalent (drops WR_implicitly_wait)."
            ),
            input_schema={
                "type": "object",
                "properties": {"actions": {"type": "array"}},
                "required": ["actions"],
            },
            handler=_tool_translate_actions_to_playwright,
        ),
        Tool(
            name="webrunner_translate_python_to_playwright",
            description=(
                "Static translator: rewrites Selenium-style Python source"
                " into Playwright equivalents; returns per-line diffs."
            ),
            input_schema={
                "type": "object",
                "properties": {"source": {"type": "string"}},
                "required": ["source"],
            },
            handler=_tool_translate_python_to_playwright,
        ),
        Tool(
            name="webrunner_pom_from_html",
            description=(
                "Discover [data-testid] / id / form fields in HTML and"
                " render a Python Page Object module."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "html": {"type": "string"},
                    "class_name": {"type": "string"},
                },
                "required": ["html"],
            },
            handler=_tool_pom_from_html,
        ),
        Tool(
            name="webrunner_scan_pii",
            description=(
                "Scan text for PII (email / phone / Luhn-card / SSN /"
                " ROC ID / IPv4); returns category + redacted preview."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "categories": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["text"],
            },
            handler=_tool_scan_pii,
        ),
        Tool(
            name="webrunner_redact_pii",
            description="Replace each detected PII match with a sentinel string.",
            input_schema={
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "replacement": {"type": "string"},
                    "categories": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["text"],
            },
            handler=_tool_redact_pii,
        ),
        Tool(
            name="webrunner_cluster_failures",
            description=(
                "Group failures by normalised error signature; returns"
                " top buckets sorted by count."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "failures": {"type": "array"},
                    "top_n": {"type": "integer"},
                },
                "required": ["failures"],
            },
            handler=_tool_cluster_failures,
        ),
        Tool(
            name="webrunner_a11y_diff",
            description=(
                "Diff two axe-core ``violations`` arrays and bucket the"
                " findings into added / resolved / persisting."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "baseline": {"type": "array"},
                    "current": {"type": "array"},
                },
                "required": ["baseline", "current"],
            },
            handler=_tool_a11y_diff,
        ),
        Tool(
            name="webrunner_score_action_locators",
            description=(
                "Score every locator referenced by an action JSON list on"
                " a 0–100 scale; lower = more fragile."
            ),
            input_schema={
                "type": "object",
                "properties": {"actions": {"type": "array"}},
                "required": ["actions"],
            },
            handler=_tool_score_action_locators,
        ),
    ]


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
