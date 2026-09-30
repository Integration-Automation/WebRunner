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
