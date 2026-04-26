"""
Integration: drive the MCP server as a real subprocess over stdio.

Spawns ``python -m je_web_runner.mcp_server`` with a piped stdin/stdout,
sends an initialize → tools/list → tools/call sequence, and asserts the
JSON-RPC envelopes round-trip the way an MCP client expects.
"""
import json
import subprocess  # nosec B404 — argv-only invocation, controlled args
import sys
import unittest


_INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2024-11-05"}}
_INITIALIZED = {"jsonrpc": "2.0", "method": "notifications/initialized"}
_LIST = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
_LOCATOR_CALL = {
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
        "name": "webrunner_locator_strength",
        "arguments": {"strategy": "ID", "value": "submit"},
    },
}
_SHUTDOWN = {"jsonrpc": "2.0", "id": 4, "method": "shutdown"}


def _spawn():
    return subprocess.Popen(  # nosec B603 — argv list, no shell
        [sys.executable, "-m", "je_web_runner.mcp_server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )


def _drive(proc, messages):
    """Send ``messages`` as the proc's input and return stdout/stderr."""
    payload = "".join(json.dumps(message) + "\n" for message in messages)
    try:
        stdout_data, stderr_data = proc.communicate(input=payload, timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            stdout_data, stderr_data = proc.communicate(timeout=5)
        except Exception:  # pylint: disable=broad-except  # nosec B110 — best-effort drain
            stdout_data, stderr_data = "", ""
    return stdout_data, stderr_data


def _parse_messages(stdout_data):
    return [
        json.loads(line)
        for line in stdout_data.splitlines()
        if line.strip()
    ]


class TestMcpSubprocess(unittest.TestCase):

    def test_init_list_call_shutdown(self):
        proc = _spawn()
        stdout_data, stderr_data = _drive(proc, [
            _INIT, _INITIALIZED, _LIST, _LOCATOR_CALL, _SHUTDOWN,
        ])
        self.assertEqual(proc.returncode, 0,
                         msg=f"non-zero exit; stderr={stderr_data!r}")
        responses = _parse_messages(stdout_data)
        ids = sorted(msg["id"] for msg in responses if "id" in msg)
        # initialize / tools/list / tools/call / shutdown all return responses;
        # notifications/initialized doesn't.
        self.assertEqual(ids, [1, 2, 3, 4])

        init_response = next(m for m in responses if m.get("id") == 1)
        self.assertEqual(init_response["result"]["serverInfo"]["name"],
                         "webrunner-mcp")

        list_response = next(m for m in responses if m.get("id") == 2)
        names = [t["name"] for t in list_response["result"]["tools"]]
        self.assertIn("webrunner_locator_strength", names)

        call_response = next(m for m in responses if m.get("id") == 3)
        text = call_response["result"]["content"][0]["text"]
        self.assertIn("score", text)

    def test_unknown_method_returns_error(self):
        proc = _spawn()
        stdout_data, _stderr = _drive(proc, [
            {"jsonrpc": "2.0", "id": 7, "method": "noSuchMethod"},
        ])
        responses = _parse_messages(stdout_data)
        match = next(m for m in responses if m.get("id") == 7)
        self.assertEqual(match["error"]["code"], -32601)


if __name__ == "__main__":
    unittest.main()
