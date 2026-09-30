"""
Integration: drive the MCP server as a real subprocess over stdio.

Spawns ``python -m je_web_runner.mcp_server`` with a piped stdin/stdout,
sends an initialize → tools/list → tools/call sequence, and asserts the
JSON-RPC envelopes round-trip the way an MCP client expects.
"""
import json
import os
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
_PING = {"jsonrpc": "2.0", "id": 4, "method": "ping"}


def _spawn():
    return subprocess.Popen(  # nosec B603 — argv list, no shell
        [sys.executable, "-m", "je_web_runner.mcp_server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",  # MCP emits UTF-8; don't let a cp1252/cp950 locale corrupt it
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

    def test_init_list_call_ping(self):
        proc = _spawn()
        stdout_data, stderr_data = _drive(proc, [
            _INIT, _INITIALIZED, _LIST, _LOCATOR_CALL, _PING,
        ])
        self.assertEqual(proc.returncode, 0,
                         msg=f"non-zero exit; stderr={stderr_data!r}")
        responses = _parse_messages(stdout_data)
        ids = sorted(msg["id"] for msg in responses if "id" in msg)
        # initialize / tools/list / tools/call / ping all return responses;
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

    def test_stdio_is_utf8_with_lf_line_ends_whatever_the_console_code_page(self):
        # The client writes UTF-8 bytes; on a cp950/cp1252 console the server used
        # to decode them with the locale code page and misplace every match.
        call = {"jsonrpc": "2.0", "id": 8, "method": "tools/call", "params": {
            "name": "webrunner_scan_pii", "arguments": {"text": "測試 alice@example.com"},
        }}
        env = {key: value for key, value in os.environ.items() if key != "PYTHONUTF8"}
        env["PYTHONIOENCODING"] = "latin-1"  # a non-UTF-8 console, reproducible on every OS
        proc = subprocess.Popen(  # nosec B603 — argv list, no shell
            [sys.executable, "-m", "je_web_runner.mcp_server"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
        )
        payload = (json.dumps(call, ensure_ascii=False) + "\n").encode("utf-8")
        stdout_data, stderr_data = proc.communicate(input=payload, timeout=30)
        self.assertEqual(proc.returncode, 0, msg=stderr_data.decode("utf-8", "replace"))
        self.assertNotIn(b"\r\n", stdout_data)
        response = json.loads(stdout_data.decode("utf-8").splitlines()[0])
        matches = json.loads(response["result"]["content"][0]["text"])
        self.assertEqual(matches[0]["start"], 3)

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
