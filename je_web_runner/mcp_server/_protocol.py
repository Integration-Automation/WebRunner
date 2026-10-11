"""
MCP 協定版本與伺服器身分 / Protocol versions and the server's identity, shared by both eras.
"""
from __future__ import annotations

from importlib import metadata
from typing import Any

#: Every revision with the ``initialize`` handshake this server speaks, newest first.
#: The server offers tools only, so the later revisions' optional features (resources,
#: prompts, elicitation, tasks) do not apply; it follows the rules they add for every
#: version: tool failures are ``isError`` results, notifications get no reply, batches
#: are rejected.
SUPPORTED_PROTOCOL_VERSIONS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")
_NEWEST_PROTOCOL_VERSION = SUPPORTED_PROTOCOL_VERSIONS[0]
#: The first revision whose ``Implementation`` carries ``description``.
DESCRIPTION_SINCE = "2025-11-25"
SERVER_DESCRIPTION = (
    "Browser automation with Selenium or Playwright: run WebRunner action lists, "
    "plus offline tools for authoring, linting and triaging them."
)
INSTRUCTIONS = (
    "WebRunner drives a real browser through action lists of [command, params] entries. "
    "Call webrunner_list_commands to see the WR_* commands, then webrunner_run_actions to run them; "
    "the browser stays open between calls until an action list runs WR_quit (Selenium) or WR_pw_quit "
    "(Playwright). A result with isError true lists the failed actions under 'failed'. The other "
    "tools (lint, format, translate, scan, shard...) work offline and never open a browser."
)

SERVER_NAME = "webrunner-mcp"
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


def server_info(protocol_version: str) -> dict[str, Any]:
    """The ``Implementation`` object for ``protocol_version`` (``description`` from 2025-11-25 on)."""
    info: dict[str, Any] = {"name": SERVER_NAME, "version": server_version()}
    if protocol_version >= DESCRIPTION_SINCE:
        info["description"] = SERVER_DESCRIPTION
    return info
