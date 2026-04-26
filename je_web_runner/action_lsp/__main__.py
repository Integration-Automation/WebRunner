"""Entry point so ``python -m je_web_runner.action_lsp`` starts the LSP.

Reconfigures stdin / stdout to suppress universal-newline translation
because Windows would otherwise rewrite the LSP framing's ``\\n`` as
``\\r\\n``, corrupting every ``Content-Length`` boundary.
"""
import sys

from je_web_runner.action_lsp.server import serve_stdio


if __name__ == "__main__":
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(newline="")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(newline="")
    serve_stdio()
