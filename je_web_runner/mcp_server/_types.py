"""
MCP 工具的型別與例外 / Tool types and errors shared by the MCP server and its tool modules.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from je_web_runner.utils.exception.exceptions import WebRunnerException


class McpServerError(WebRunnerException):
    """Raised when the server encounters a fatal protocol error."""


class McpInvalidParams(McpServerError):
    """A request's params are unusable (unknown tool, arguments not an object); JSON-RPC -32602."""


#: ``annotations`` for a tool that only computes or reads local input: no side effects.
READ_ONLY = {"readOnlyHint": True, "openWorldHint": False}
#: ``annotations`` for a tool that drives a real browser against arbitrary sites.
DRIVES_BROWSER = {
    "readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True,
}


@dataclass
class Tool:
    """
    一個 MCP 工具：名稱、說明、參數 schema 與處理函式
    One MCP tool. ``title``, ``annotations`` (MCP 2025-03-26+) and ``output_schema``
    (2025-06-18+) are optional and only sent when set.
    """
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[[dict[str, Any]], Any]
    title: str | None = None
    annotations: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None

    def schema(self) -> dict[str, Any]:
        """The tool as ``tools/list`` sends it."""
        schema: dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }
        if self.title:
            schema["title"] = self.title
        if self.annotations:
            schema["annotations"] = self.annotations
        if self.output_schema:
            schema["outputSchema"] = self.output_schema
        return schema


@dataclass
class ToolResult:
    """
    工具回傳值加上是否失敗（送出時成為 ``isError``）
    A handler's value plus whether it reports a failure, sent as the result's ``isError``.
    Handlers may also return a bare value (success) or raise (failure).
    """
    value: Any
    is_error: bool = False
