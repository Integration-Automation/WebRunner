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


class TestMcpSubprocess(unittest.TestCase):

    def test_init_list_call_shutdown(self):
        proc = subprocess.Popen(  # nosec B603 — argv list, no shell
            [sys.executable, "-m", "je_web_runner.mcp_server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        try:
            self._send(proc, _INIT)
            self._send(proc, _INITIALIZED)
            self._send(proc, _LIST)
            self._send(proc, _LOCATOR_CALL)
            self._send(proc, _SHUTDOWN)
            assert proc.stdin is not None  # nosec B101 — typing guard
            proc.stdin.close()
            stdout_data, stderr_data = proc.communicate(timeout=10)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.communicate(timeout=5)
        self.assertEqual(proc.returncode, 0,
                         msg=f"non-zero exit; stderr={stderr_data!r}")
        responses = self._parse_messages(stdout_data)
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
        proc = subprocess.Popen(  # nosec B603 — argv list, no shell
            [sys.executable, "-m", "je_web_runner.mcp_server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        try:
            self._send(proc, {"jsonrpc": "2.0", "id": 7, "method": "noSuchMethod"})
            assert proc.stdin is not None  # nosec B101 — typing guard
            proc.stdin.close()
            stdout_data, _stderr = proc.communicate(timeout=10)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.communicate(timeout=5)
        responses = self._parse_messages(stdout_data)
        match = next(m for m in responses if m.get("id") == 7)
        self.assertEqual(match["error"]["code"], -32601)

    @staticmethod
    def _send(proc, message):
        assert proc.stdin is not None  # nosec B101 — typing guard
        proc.stdin.write(json.dumps(message) + "\n")
        proc.stdin.flush()

    @staticmethod
    def _parse_messages(stdout_data):
        return [
            json.loads(line)
            for line in stdout_data.splitlines()
            if line.strip()
        ]


if __name__ == "__main__":
    unittest.main()
