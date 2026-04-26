import io
import json
import unittest

from je_web_runner.mcp_server.server import (
    McpServer,
    Tool,
    build_default_tools,
    make_default_server,
    serve_stdio,
)


def _tool(name="echo", handler=None):
    return Tool(
        name=name,
        description="echo back",
        input_schema={"type": "object", "properties": {"text": {"type": "string"}}},
        handler=handler or (lambda args: args.get("text", "")),
    )


class TestMcpServer(unittest.TestCase):

    def test_initialize_returns_server_info(self):
        server = McpServer()
        result = server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                "params": {"protocolVersion": "2024-11-05"}})
        self.assertEqual(result["id"], 1)
        info = result["result"]["serverInfo"]
        self.assertEqual(info["name"], "webrunner-mcp")

    def test_tools_list(self):
        server = McpServer()
        server.register(_tool())
        result = server.handle({"id": 2, "method": "tools/list"})
        names = [t["name"] for t in result["result"]["tools"]]
        self.assertIn("echo", names)

    def test_tools_call_success(self):
        server = McpServer()
        server.register(_tool(handler=lambda args: {"got": args.get("text")}))
        result = server.handle({"id": 3, "method": "tools/call",
                                "params": {"name": "echo", "arguments": {"text": "hi"}}})
        content = result["result"]["content"]
        self.assertEqual(content[0]["type"], "text")
        self.assertIn('"got": "hi"', content[0]["text"])
        self.assertFalse(result["result"]["isError"])

    def test_unknown_tool(self):
        server = McpServer()
        result = server.handle({"id": 4, "method": "tools/call",
                                "params": {"name": "ghost", "arguments": {}}})
        self.assertIn("error", result)

    def test_unknown_method(self):
        server = McpServer()
        result = server.handle({"id": 5, "method": "noSuch"})
        self.assertEqual(result["error"]["code"], -32601)

    def test_notifications_initialized_no_response(self):
        server = McpServer()
        self.assertIsNone(server.handle({"method": "notifications/initialized"}))
        self.assertTrue(server.initialized)

    def test_method_must_be_string(self):
        server = McpServer()
        result = server.handle({"id": 9, "method": 42})
        self.assertEqual(result["error"]["code"], -32600)


class TestStdioLoop(unittest.TestCase):

    def test_round_trip(self):
        server = McpServer()
        server.register(_tool())
        stdin = io.StringIO(
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                        "params": {"protocolVersion": "2024-11-05"}}) + "\n"
            + json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}) + "\n"
        )
        stdout = io.StringIO()
        serve_stdio(stdin=stdin, stdout=stdout, server=server)
        lines = [json.loads(line) for line in stdout.getvalue().splitlines() if line]
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0]["id"], 1)
        self.assertEqual(lines[1]["id"], 2)


class TestDefaultTools(unittest.TestCase):

    def test_default_tools_registered(self):
        server = make_default_server()
        self.assertIn("webrunner_lint_action", server.tools)
        self.assertIn("webrunner_locator_strength", server.tools)

    def test_locator_strength_runs(self):
        server = make_default_server()
        result = server.handle({"id": 1, "method": "tools/call", "params": {
            "name": "webrunner_locator_strength",
            "arguments": {"strategy": "ID", "value": "submit"},
        }})
        text = result["result"]["content"][0]["text"]
        self.assertIn("score", text)

    def test_render_template_runs(self):
        server = make_default_server()
        result = server.handle({"id": 1, "method": "tools/call", "params": {
            "name": "webrunner_render_template",
            "arguments": {
                "template": "switch_locale",
                "parameters": {"base_url": "https://x.com/", "locale": "en"},
            },
        }})
        self.assertFalse(result["result"]["isError"])

    def test_default_tools_inputschemas(self):
        for tool in build_default_tools():
            self.assertEqual(tool.input_schema["type"], "object")


if __name__ == "__main__":
    unittest.main()
