"""
MCP 呼叫端的安全政策 / What an MCP caller may do.

An MCP client is a model acting on text it read, so the server refuses the
commands that would let it widen its own powers, and can fence the file tools
to one directory:

* ``WR_add_package_to_executor`` / ``WR_add_package_to_callback_executor`` import
  any Python package and expose its functions, ``os`` and ``subprocess`` included;
* ``WR_set_allow_arbitrary_script`` would re-open a script gate the operator closed.

``WEBRUNNER_MCP_ALLOW_UNSAFE_COMMANDS=1`` lifts the refusal. ``WEBRUNNER_MCP_ROOT``,
when set, is the only directory ``webrunner_run_action_files`` and
``webrunner_compute_trend`` may read from.
"""
from __future__ import annotations

import os
from pathlib import Path

from je_web_runner.mcp_server._types import McpServerError

UNSAFE_COMMANDS = frozenset({
    "WR_add_package_to_executor",
    "WR_add_package_to_callback_executor",
    "WR_set_allow_arbitrary_script",
})
ALLOW_UNSAFE_ENV = "WEBRUNNER_MCP_ALLOW_UNSAFE_COMMANDS"
ROOT_ENV = "WEBRUNNER_MCP_ROOT"
_TRUE = {"1", "true", "yes", "on"}


def denied_commands() -> frozenset[str]:
    """The commands an MCP call may not run: :data:`UNSAFE_COMMANDS` unless the operator lifted it."""
    if os.environ.get(ALLOW_UNSAFE_ENV, "").strip().lower() in _TRUE:
        return frozenset()
    return UNSAFE_COMMANDS


def checked_path(path: str) -> str:
    """
    檢查檔案路徑是否在 ``WEBRUNNER_MCP_ROOT`` 之內
    Return ``path`` when ``WEBRUNNER_MCP_ROOT`` is unset or ``path`` resolves inside it
    (``..`` and symlinks are resolved first); raise :class:`McpServerError` otherwise.
    """
    root = os.environ.get(ROOT_ENV)
    if not root:
        return path
    resolved_root = Path(root).resolve()
    resolved = Path(path).resolve()
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise McpServerError(f"{path!r} is outside {ROOT_ENV} ({resolved_root})")
    return str(resolved)
