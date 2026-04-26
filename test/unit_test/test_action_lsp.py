import io
import json
import unittest

from je_web_runner.action_lsp.server import (
    ActionLspServer,
    serve_stdio,
)


def _frame(message):
    body = json.dumps(message)
    return f"Content-Length: {len(body.encode('utf-8'))}\r\n\r\n{body}"


class TestActionLspServer(unittest.TestCase):

    def test_initialize_returns_capabilities(self):
        server = ActionLspServer()
        result = server.handle({"id": 1, "method": "initialize", "params": {}})
        capabilities = result["result"]["capabilities"]
        self.assertEqual(capabilities["textDocumentSync"], 1)
        self.assertIn("triggerCharacters", capabilities["completionProvider"])

    def test_did_open_publishes_diagnostics(self):
        server = ActionLspServer()
        result = server.handle({
            "method": "textDocument/didOpen",
            "params": {"textDocument": {
                "uri": "file:///x.json",
                "text": "not json",
            }},
        })
        self.assertEqual(result["method"], "textDocument/publishDiagnostics")
        diags = result["params"]["diagnostics"]
        self.assertTrue(any("JSON parse error" in d["message"] for d in diags))

    def test_did_open_clean_array_no_diagnostics(self):
        server = ActionLspServer()
        result = server.handle({
            "method": "textDocument/didOpen",
            "params": {"textDocument": {
                "uri": "file:///x.json",
                "text": "[]",
            }},
        })
        self.assertEqual(result["params"]["diagnostics"], [])

    def test_root_must_be_array(self):
        server = ActionLspServer()
        result = server.handle({
            "method": "textDocument/didOpen",
            "params": {"textDocument": {
                "uri": "file:///x.json",
                "text": "{}",
            }},
        })
        diags = result["params"]["diagnostics"]
        self.assertTrue(any("root must be a JSON array" in d["message"] for d in diags))

    def test_did_change_updates_text(self):
        server = ActionLspServer()
        server.handle({
            "method": "textDocument/didOpen",
            "params": {"textDocument": {"uri": "file:///x.json", "text": "[]"}},
        })
        server.handle({
            "method": "textDocument/didChange",
            "params": {
                "textDocument": {"uri": "file:///x.json", "version": 2},
                "contentChanges": [{"text": "not json"}],
            },
        })
        self.assertEqual(server.documents["file:///x.json"].text, "not json")

    def test_completion_returns_command_names(self):
        server = ActionLspServer()
        # Stub command list so the test doesn't depend on full executor state
        server._command_names = ["WR_quit_all", "WR_to_url"]
        result = server.handle({"id": 5, "method": "textDocument/completion",
                                "params": {}})
        labels = [item["label"] for item in result["result"]["items"]]
        self.assertEqual(set(labels), {"WR_quit_all", "WR_to_url"})

    def test_unknown_method_returns_error(self):
        server = ActionLspServer()
        result = server.handle({"id": 9, "method": "noSuch"})
        self.assertEqual(result["error"]["code"], -32601)


class TestServeStdio(unittest.TestCase):

    def test_round_trip(self):
        message_a = _frame({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                            "params": {}})
        message_b = _frame({"jsonrpc": "2.0", "method": "exit"})
        stdin = io.StringIO(message_a + message_b)
        stdout = io.StringIO()
        serve_stdio(stdin=stdin, stdout=stdout)
        output = stdout.getvalue()
        self.assertIn("Content-Length:", output)
        self.assertIn('"jsonrpc": "2.0"', output)


if __name__ == "__main__":
    unittest.main()
