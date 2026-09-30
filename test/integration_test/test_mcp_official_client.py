"""
The MCP server driven by the official ``mcp`` client over stdio, in both protocol eras.

The server is hand-rolled; this checks it against the reference implementation of the
wire protocol: the 2.x client's handshake (``initialize``) and its stateless
2026-07-28 probe (``server/discover``), then ``tools/list`` and ``tools/call``
including a result validated against the tool's ``outputSchema``.
"""
import asyncio
import os
import sys
from pathlib import Path

import pytest

mcp = pytest.importorskip("mcp", reason="the official MCP client is a dev dependency")
from mcp.client.stdio import stdio_client  # noqa: E402  (after the importorskip guard)

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _server_params(cwd: Path) -> "mcp.StdioServerParameters":
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(_REPO_ROOT), env.get("PYTHONPATH")]))
    # cwd: importing je_web_runner opens WEBRunner.log in the working directory.
    return mcp.StdioServerParameters(
        command=sys.executable, args=["-m", "je_web_runner.mcp_server"], env=env, cwd=str(cwd),
    )


async def _exercise(session: "mcp.ClientSession") -> dict:
    tools = {tool.name: tool for tool in (await session.list_tools()).tools}
    strength = await session.call_tool(
        "webrunner_locator_strength", {"strategy": "ID", "value": "submit"})
    run = await session.call_tool("webrunner_run_actions", {"actions": [["WR_sleep", {"seconds": 0}]]})
    bad = await session.call_tool("webrunner_partition_shard", {"paths": ["a"], "index": "x", "total": 2})
    return {"tools": tools, "strength": strength, "run": run, "bad": bad}


async def _handshake(cwd: Path) -> dict:
    async with stdio_client(_server_params(cwd)) as (read, write), mcp.ClientSession(read, write) as session:
        initialized = await session.initialize()
        return {"version": initialized.protocol_version, **await _exercise(session)}


async def _stateless(cwd: Path) -> dict:
    async with stdio_client(_server_params(cwd)) as (read, write), mcp.ClientSession(read, write) as session:
        discovered = await session.discover()
        return {"versions": discovered.supported_versions, **await _exercise(session)}


def _assert_tools_work(outcome: dict) -> None:
    assert len(outcome["tools"]) == 22  # nosec B101
    assert outcome["tools"]["webrunner_run_actions"].annotations.destructive_hint is True  # nosec B101
    assert outcome["strength"].is_error is False  # nosec B101
    assert outcome["run"].is_error is False  # nosec B101
    assert outcome["run"].structured_content["failed"] == []  # nosec B101
    assert outcome["bad"].is_error is True  # nosec B101


def test_handshake_era_round_trip(tmp_path):
    outcome = asyncio.run(_handshake(tmp_path))
    assert outcome["version"] == "2025-11-25"  # nosec B101
    _assert_tools_work(outcome)


def test_stateless_era_round_trip(tmp_path):
    outcome = asyncio.run(_stateless(tmp_path))
    assert "2026-07-28" in outcome["versions"]  # nosec B101
    _assert_tools_work(outcome)
