"""
MCP 2026-07-28（無狀態版）/ The stateless revision, served beside the handshake-era ones.

2026-07-28 removes ``initialize``: every request names its protocol version and the
client's capabilities in ``params._meta``, every result says it is complete
(``resultType``) and carries the server's identity in ``_meta``, and
``server/discover`` replaces the handshake as the way to learn the server's versions
and capabilities. A dual-era server decides per request: one whose ``_meta`` names a
protocol version is served statelessly; ``initialize`` and every request without that
key are served the way the older revisions define. Ported from AutoControlGUI's
``utils/mcp_server/_stateless.py``, without the parts this tools-only server has no
use for (subscriptions, resources, prompts, confirmation round trips).
"""
from __future__ import annotations

from typing import Any

from je_web_runner.mcp_server._protocol import SUPPORTED_PROTOCOL_VERSIONS
from je_web_runner.mcp_server._types import McpInvalidParams, McpProtocolError

STATELESS_PROTOCOL_VERSION = "2026-07-28"
META_PROTOCOL_VERSION = "io.modelcontextprotocol/protocolVersion"
META_CLIENT_CAPABILITIES = "io.modelcontextprotocol/clientCapabilities"
META_SERVER_INFO = "io.modelcontextprotocol/serverInfo"
#: ``UnsupportedProtocolVersionError``; its ``data`` lists the supported versions.
UNSUPPORTED_PROTOCOL_VERSION = -32022
DISCOVER_METHOD = "server/discover"
#: ``ttlMs`` of the cacheable results: the tool list is fixed once the server runs.
_CACHE_TTL_MS = {DISCOVER_METHOD: 3_600_000, "tools/list": 3_600_000}
_CAPABILITIES = {"tools": {}}


def all_supported_versions() -> list[str]:
    """Every revision this server speaks, stateless first, then the handshake era, newest first."""
    return [STATELESS_PROTOCOL_VERSION, *SUPPORTED_PROTOCOL_VERSIONS]


def stateless_version(params: dict[str, Any]) -> str | None:
    """
    讀出請求宣告的 2026-07-28 版本；舊時代的請求回傳 ``None``
    The 2026-07-28 version a request declares in ``_meta``, or ``None`` for a
    handshake-era request. Raises ``-32022`` for a version this server does not serve
    statelessly and ``-32602`` when the client capabilities are missing.
    """
    meta = params.get("_meta")
    if not isinstance(meta, dict) or META_PROTOCOL_VERSION not in meta:
        return None
    version = meta[META_PROTOCOL_VERSION]
    if version != STATELESS_PROTOCOL_VERSION:
        raise McpProtocolError(
            UNSUPPORTED_PROTOCOL_VERSION, "Unsupported protocol version",
            data={"supported": all_supported_versions(), "requested": version},
        )
    if not isinstance(meta.get(META_CLIENT_CAPABILITIES), dict):
        raise McpInvalidParams(f"_meta must carry {META_CLIENT_CAPABILITIES} as an object")
    return version


def discover_result(instructions: str) -> dict[str, Any]:
    """The body of a ``server/discover`` result, before :func:`shape_result`."""
    return {
        "supportedVersions": all_supported_versions(),
        "capabilities": _CAPABILITIES,
        "instructions": instructions,
    }


def shape_result(method: str, result: dict[str, Any], server_info: dict[str, Any]) -> dict[str, Any]:
    """
    加上每個 2026-07-28 結果都要有的欄位
    Add what every 2026-07-28 result carries: ``resultType``, the server's identity in
    ``_meta``, and ``ttlMs`` / ``cacheScope`` on the cacheable results. ``private``:
    the tool list and instructions describe this installation.
    """
    shaped = dict(result)
    shaped.setdefault("resultType", "complete")
    shaped["_meta"] = {**(shaped.get("_meta") or {}), META_SERVER_INFO: server_info}
    if method in _CACHE_TTL_MS:
        shaped["ttlMs"] = _CACHE_TTL_MS[method]
        shaped["cacheScope"] = "private"
    return shaped
