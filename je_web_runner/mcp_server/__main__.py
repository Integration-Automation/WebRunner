"""Entry point so ``python -m je_web_runner.mcp_server`` starts the stdio server."""
from je_web_runner.mcp_server.server import serve_stdio


if __name__ == "__main__":
    serve_stdio()
