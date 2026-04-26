"""WebRunner MCP server: expose WR_* actions over the Model Context Protocol."""
from je_web_runner.mcp_server.browser_tools import build_browser_tools
from je_web_runner.mcp_server.server import (
    McpServer,
    McpServerError,
    build_default_tools,
    serve_stdio,
)

__all__ = [
    "McpServer", "McpServerError",
    "build_default_tools", "build_browser_tools", "serve_stdio",
]
