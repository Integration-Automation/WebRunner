"""
Integration: drive the Action JSON LSP as a real subprocess.

Frames messages with the LSP-required ``Content-Length`` headers and
walks initialize → didOpen (with a JSON parse error) →
publishDiagnostics → exit.

Note: the subprocess pipes use binary mode. ``text=True`` would convert
``\\n`` to ``\\r\\n`` on Windows, corrupting the framing.
"""
import json
import subprocess  # nosec B404 — argv-only invocation, controlled args
import sys
import unittest


def _frame(message) -> bytes:
    body = json.dumps(message).encode("utf-8")
    header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
    return header + body


def _read_messages(stream_bytes: bytes):
    """Parse a stream of LSP-framed messages from raw bytes."""
    messages = []
    cursor = 0
    while cursor < len(stream_bytes):
        header_end = stream_bytes.find(b"\r\n\r\n", cursor)
        if header_end == -1:
            break
        headers = stream_bytes[cursor:header_end].decode("ascii", errors="replace")
        body_start = header_end + 4
        length = 0
        for header_line in headers.split("\r\n"):
            if ":" in header_line:
                name, _, value = header_line.partition(":")
                if name.strip().lower() == "content-length":
                    length = int(value.strip())
        body = stream_bytes[body_start:body_start + length]
        if body:
            messages.append(json.loads(body.decode("utf-8")))
        cursor = body_start + length
    return messages


def _spawn():
    return subprocess.Popen(  # nosec B603 — argv list, no shell
        [sys.executable, "-m", "je_web_runner.action_lsp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
    )


class TestActionLspSubprocess(unittest.TestCase):

    def test_initialize_didopen_publishes_diagnostics(self):
        proc = _spawn()
        try:
            assert proc.stdin is not None
            proc.stdin.write(_frame({"jsonrpc": "2.0", "id": 1,
                                     "method": "initialize", "params": {}}))
            proc.stdin.write(_frame({"jsonrpc": "2.0",
                                     "method": "textDocument/didOpen",
                                     "params": {"textDocument": {
                                         "uri": "file:///x.json",
                                         "text": "this is not json",
                                     }}}))
            proc.stdin.write(_frame({"jsonrpc": "2.0", "method": "exit"}))
            proc.stdin.flush()
            proc.stdin.close()
            stdout_data, stderr_data = proc.communicate(timeout=10)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.communicate(timeout=5)
        self.assertEqual(proc.returncode, 0,
                         msg=f"stderr={stderr_data!r}")
        messages = _read_messages(stdout_data)
        self.assertGreaterEqual(len(messages), 2,
                                msg=f"raw stdout: {stdout_data!r}")
        init_response = next(m for m in messages if m.get("id") == 1)
        self.assertIn("capabilities", init_response["result"])
        diagnostics_msg = next(
            m for m in messages
            if m.get("method") == "textDocument/publishDiagnostics"
        )
        diags = diagnostics_msg["params"]["diagnostics"]
        self.assertTrue(diags)
        self.assertIn("JSON parse error", diags[0]["message"])

    def test_completion_returns_command_names(self):
        proc = _spawn()
        try:
            assert proc.stdin is not None
            proc.stdin.write(_frame({"jsonrpc": "2.0", "id": 1,
                                     "method": "initialize", "params": {}}))
            proc.stdin.write(_frame({"jsonrpc": "2.0", "id": 2,
                                     "method": "textDocument/completion",
                                     "params": {}}))
            proc.stdin.write(_frame({"jsonrpc": "2.0", "method": "exit"}))
            proc.stdin.flush()
            proc.stdin.close()
            stdout_data, _stderr = proc.communicate(timeout=10)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.communicate(timeout=5)
        messages = _read_messages(stdout_data)
        completion = next(m for m in messages if m.get("id") == 2)
        labels = [item["label"] for item in completion["result"]["items"]]
        self.assertTrue(any(name.startswith("WR_") for name in labels))


if __name__ == "__main__":
    unittest.main()
