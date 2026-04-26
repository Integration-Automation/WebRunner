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

    def test_full_default_tool_surface(self):
        # The MCP server is the public LLM-facing surface; freeze the tool
        # list here so accidental removals fail loudly in review.
        names = {tool.name for tool in build_default_tools()}
        self.assertEqual(names, {
            "webrunner_lint_action",
            "webrunner_locator_strength",
            "webrunner_render_template",
            "webrunner_compute_trend",
            "webrunner_validate_response",
            "webrunner_summary_markdown",
            "webrunner_diff_shard",
            "webrunner_render_k8s",
            "webrunner_partition_shard",
            "webrunner_format_actions",
            "webrunner_parse_markdown",
            "webrunner_translate_actions_to_playwright",
            "webrunner_translate_python_to_playwright",
            "webrunner_pom_from_html",
            "webrunner_scan_pii",
            "webrunner_redact_pii",
            "webrunner_cluster_failures",
            "webrunner_a11y_diff",
            "webrunner_score_action_locators",
        })

    def test_browser_tools_registered_in_default_server(self):
        # Browser execution tools are merged into the default server so MCP
        # clients can drive Selenium / Playwright through WR_* actions.
        server = make_default_server()
        for name in (
            "webrunner_run_actions",
            "webrunner_run_action_files",
            "webrunner_list_commands",
        ):
            self.assertIn(name, server.tools)


class TestNewTools(unittest.TestCase):

    def setUp(self):
        self.server = make_default_server()

    def _call(self, name, arguments):
        return self.server.handle({"id": 1, "method": "tools/call", "params": {
            "name": name, "arguments": arguments,
        }})

    def test_format_actions(self):
        result = self._call("webrunner_format_actions",
                            {"actions": [["WR_quit_all"]]})
        self.assertFalse(result["result"]["isError"])
        self.assertIn('["WR_quit_all"]', result["result"]["content"][0]["text"])

    def test_parse_markdown(self):
        result = self._call("webrunner_parse_markdown",
                            {"text": "- open https://example.com\n- quit"})
        body = result["result"]["content"][0]["text"]
        self.assertIn("WR_to_url", body)
        self.assertIn("WR_quit_all", body)

    def test_translate_actions_to_playwright(self):
        result = self._call("webrunner_translate_actions_to_playwright", {
            "actions": [["WR_to_url", {"url": "https://x"}]],
        })
        self.assertIn("WR_pw_to_url", result["result"]["content"][0]["text"])

    def test_translate_python_to_playwright(self):
        result = self._call("webrunner_translate_python_to_playwright", {
            "source": "driver.get('https://x.com')",
        })
        self.assertIn("page.goto", result["result"]["content"][0]["text"])

    def test_pom_from_html(self):
        html = '<button data-testid="primary-cta">Go</button>'
        result = self._call("webrunner_pom_from_html",
                            {"html": html, "class_name": "Login"})
        body = result["result"]["content"][0]["text"]
        self.assertIn("class Login", body)
        self.assertIn("primary_cta", body)

    def test_scan_pii(self):
        result = self._call("webrunner_scan_pii",
                            {"text": "email alice@example.com here"})
        body = result["result"]["content"][0]["text"]
        self.assertIn("email", body)

    def test_redact_pii(self):
        result = self._call("webrunner_redact_pii", {
            "text": "email alice@example.com here",
            "replacement": "[X]",
        })
        self.assertIn("[X]", result["result"]["content"][0]["text"])

    def test_cluster_failures(self):
        result = self._call("webrunner_cluster_failures", {
            "failures": [
                {"function_name": "a", "exception": "TimeoutError at 0xab"},
                {"function_name": "b", "exception": "TimeoutError at 0xcd"},
            ]
        })
        body = result["result"]["content"][0]["text"]
        self.assertIn('"count": 2', body)

    def test_a11y_diff(self):
        result = self._call("webrunner_a11y_diff", {
            "baseline": [],
            "current": [{
                "id": "label",
                "impact": "serious",
                "nodes": [{"target": ["input.email"]}],
            }],
        })
        body = result["result"]["content"][0]["text"]
        self.assertIn('"regressed": true', body)

    def test_score_action_locators(self):
        result = self._call("webrunner_score_action_locators", {
            "actions": [
                ["WR_save_test_object",
                 {"test_object_name": "submit", "object_type": "ID"}],
            ],
        })
        body = result["result"]["content"][0]["text"]
        self.assertIn("score", body)


class TestBrowserTools(unittest.TestCase):
    """Tools that call the executor — covered without launching a browser."""

    def setUp(self):
        self.server = make_default_server()

    def _call(self, name, arguments):
        return self.server.handle({"id": 1, "method": "tools/call", "params": {
            "name": name, "arguments": arguments,
        }})

    def test_run_actions_rejects_non_list(self):
        result = self._call("webrunner_run_actions", {"actions": "nope"})
        self.assertTrue(result["result"]["isError"])

    def test_run_action_files_rejects_non_string_paths(self):
        result = self._call("webrunner_run_action_files", {"files": [123]})
        self.assertTrue(result["result"]["isError"])

    def test_list_commands_returns_wr_surface(self):
        result = self._call("webrunner_list_commands", {})
        body = result["result"]["content"][0]["text"]
        self.assertIn("WR_to_url", body)
        self.assertIn("WR_quit", body)

    def test_run_actions_captures_stdout_and_executes_safe_command(self):
        # WR_sleep with 0 seconds is a side-effect-free executor call that
        # returns a numeric value — perfect for checking the wiring without
        # launching a browser.
        result = self._call("webrunner_run_actions",
                            {"actions": [["WR_sleep", {"seconds": 0}]]})
        self.assertFalse(result["result"]["isError"])
        body = result["result"]["content"][0]["text"]
        self.assertIn('"stdout"', body)
        self.assertIn('"record"', body)
        self.assertIn("WR_sleep", body)


if __name__ == "__main__":
    unittest.main()
