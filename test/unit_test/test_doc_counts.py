"""The counts quoted in the docs must match the code.

Counts in prose drift: the README said the MCP runner covered "~280" commands when the executor had
444 `WR_*` commands. Each row below names a document, a pattern with one number in it, and how to
measure that number. A failure means either the number moved and the document was not updated, or the
sentence was reworded and the pattern here has to follow it; the message says which.
"""
import pathlib
import re
from typing import Callable, List, Tuple

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _wr_commands() -> int:
    from je_web_runner.utils.executor.action_executor import executor
    return sum(1 for name in executor.event_dict if name.startswith("WR_"))


def _mcp_tools() -> int:
    from je_web_runner.mcp_server.browser_tools import build_browser_tools
    from je_web_runner.mcp_server.server import build_default_tools
    return len(build_default_tools()) + len(build_browser_tools())


def _safe_builtins() -> int:
    from je_web_runner.utils.executor.action_executor import SAFE_BUILTINS
    return len(SAFE_BUILTINS)


# (document, regex with one capture group, what it counts, how to measure it)
CITATIONS: List[Tuple[str, str, str, Callable[[], int]]] = [
    ("README.md", r"Covers all (\d+) `WR_\*` commands", "WR_* commands", _wr_commands),
    ("README.md", r"The default tool list \((\d+) tools\)", "MCP tools", _mcp_tools),
    ("architecture.md", r"the (\d+)-name `SAFE_BUILTINS` allowlist", "SAFE_BUILTINS", _safe_builtins),
    ("docs/source/Eng/doc/mcp_claude/mcp_claude_doc.rst", r"registers (\d+) tools", "MCP tools", _mcp_tools),
    ("docs/source/Eng/doc/mcp_claude/mcp_claude_doc.rst", r"executor, (\d+) of them", "WR_* commands", _wr_commands),
    ("docs/source/Zh/doc/mcp_claude/mcp_claude_doc.rst", r"預設註冊 (\d+) 個工具", "MCP tools", _mcp_tools),
    ("docs/source/Zh/doc/mcp_claude/mcp_claude_doc.rst", r"共 (\d+) 個\)", "WR_* commands", _wr_commands),
]


@pytest.mark.parametrize("document, pattern, label, measure", CITATIONS,
                         ids=[f"{doc}:{label}" for doc, _, label, _ in CITATIONS])
def test_quoted_count_matches_the_code(document, pattern, label, measure):
    text = (ROOT / document).read_text(encoding="utf-8")
    quoted = [int(number) for number in re.findall(pattern, text)]
    assert quoted, f"{document}: no sentence matches {pattern!r} any more; update the pattern to the new wording"  # nosec B101
    actual = measure()
    assert all(number == actual for number in quoted), (  # nosec B101
        f"{document} quotes {quoted} {label}, the code has {actual}: update the document")
