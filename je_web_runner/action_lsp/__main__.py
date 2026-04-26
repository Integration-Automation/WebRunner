"""Entry point so ``python -m je_web_runner.action_lsp`` starts the LSP."""
from je_web_runner.action_lsp.server import serve_stdio


if __name__ == "__main__":
    serve_stdio()
