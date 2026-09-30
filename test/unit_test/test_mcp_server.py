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

    def test_initialize_echoes_a_supported_protocol_version(self):
        for version in ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05"):
            result = McpServer().handle({"id": 1, "method": "initialize",
                                         "params": {"protocolVersion": version}})
            self.assertEqual(result["result"]["protocolVersion"], version)

    def test_initialize_answers_an_unknown_version_with_the_newest(self):
        result = McpServer().handle({"id": 1, "method": "initialize",
                                     "params": {"protocolVersion": "1999-01-01"}})
        self.assertEqual(result["result"]["protocolVersion"], "2025-11-25")

    def test_initialize_reports_package_version_instructions_and_only_tools(self):
        from je_web_runner.mcp_server.server import server_version
        result = McpServer().handle({"id": 1, "method": "initialize",
                                     "params": {"protocolVersion": "2025-11-25"}})["result"]
        self.assertEqual(result["serverInfo"]["version"], server_version())
        self.assertNotEqual(result["serverInfo"]["version"], "0.1.0")
        self.assertIn("webrunner_list_commands", result["instructions"])
        self.assertEqual(set(result["capabilities"]), {"tools"})
        self.assertIn("description", result["serverInfo"])

    def test_server_description_only_from_2025_11_25(self):
        result = McpServer().handle({"id": 1, "method": "initialize",
                                     "params": {"protocolVersion": "2024-11-05"}})["result"]
        self.assertNotIn("description", result["serverInfo"])

    def test_resources_and_shutdown_are_not_offered(self):
        server = McpServer()
        for method in ("resources/list", "shutdown"):
            result = server.handle({"id": 7, "method": method})
            self.assertEqual(result["error"]["code"], -32601, method)

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

    def test_unknown_notification_gets_no_reply(self):
        # JSON-RPC: a message without "id" is a notification and must never be answered.
        server = McpServer()
        self.assertIsNone(server.handle({"jsonrpc": "2.0", "method": "notifications/cancelled",
                                         "params": {"requestId": 1}}))
        self.assertIsNone(server.handle({"jsonrpc": "2.0", "method": 42}))

    def test_unknown_tool_is_invalid_params(self):
        server = McpServer()
        result = server.handle({"id": 4, "method": "tools/call",
                                "params": {"name": "ghost", "arguments": {}}})
        self.assertEqual(result["error"]["code"], -32602)

    def test_non_object_arguments_are_invalid_params(self):
        server = McpServer()
        server.register(_tool())
        result = server.handle({"id": 4, "method": "tools/call",
                                "params": {"name": "echo", "arguments": [1]}})
        self.assertEqual(result["error"]["code"], -32602)

    def test_handler_failure_is_a_tool_error_not_a_protocol_error(self):
        def boom(_args):
            raise ValueError("index must be an integer")
        server = McpServer()
        server.register(_tool(handler=boom))
        result = server.handle({"id": 5, "method": "tools/call",
                                "params": {"name": "echo", "arguments": {}}})
        self.assertNotIn("error", result)
        self.assertTrue(result["result"]["isError"])
        self.assertIn("index must be an integer", result["result"]["content"][0]["text"])


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

    def test_batch_is_rejected_with_one_error(self):
        # JSON-RPC batching was removed from MCP in 2025-06-18.
        server = McpServer()
        server.register(_tool())
        stdin = io.StringIO(json.dumps([
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        ]) + "\n")
        stdout = io.StringIO()
        serve_stdio(stdin=stdin, stdout=stdout, server=server)
        lines = [json.loads(line) for line in stdout.getvalue().splitlines() if line]
        self.assertEqual(len(lines), 1)
        self.assertIsNone(lines[0]["id"])
        self.assertEqual(lines[0]["error"]["code"], -32600)


class TestPackageExports(unittest.TestCase):

    def test_package_exports_what_the_readme_imports(self):
        # README › MCP Server: from je_web_runner.mcp_server import McpServer, Tool, ...
        import je_web_runner.mcp_server as package
        for name in ("McpServer", "Tool", "ToolResult", "build_default_tools", "serve_stdio"):
            self.assertIn(name, package.__all__)
            self.assertTrue(hasattr(package, name))


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

    def test_run_actions_reports_a_failed_action_as_tool_error(self):
        result = self._call("webrunner_run_actions",
                            {"actions": [["WR_sleep", {"seconds": 0}], ["WR_no_such_command"]]})
        self.assertTrue(result["result"]["isError"])
        payload = json.loads(result["result"]["content"][0]["text"])
        self.assertEqual(payload["failed"], ["execute: ['WR_no_such_command']"])
        self.assertEqual(len(payload["record"]), 2)

    def test_run_actions_returns_structured_content(self):
        result = self._call("webrunner_run_actions", {"actions": [["WR_sleep", {"seconds": 0}]]})["result"]
        self.assertEqual(result["structuredContent"], json.loads(result["content"][0]["text"]))
        self.assertEqual(result["structuredContent"]["failed"], [])


class TestToolMetadata(unittest.TestCase):
    """Every shipped tool carries what MCP 2025-06-18+ clients use to present and gate it."""

    def setUp(self):
        self.tools = make_default_server()._tools_list()["tools"]  # pylint: disable=protected-access

    def test_every_tool_has_a_title_and_annotations(self):
        for tool in self.tools:
            self.assertTrue(tool.get("title"), tool["name"])
            self.assertIn("readOnlyHint", tool["annotations"], tool["name"])

    def test_only_the_browser_tools_have_side_effects(self):
        browser = {"webrunner_run_actions", "webrunner_run_action_files"}
        for tool in self.tools:
            hints = tool["annotations"]
            if tool["name"] in browser:
                self.assertFalse(hints["readOnlyHint"], tool["name"])
                self.assertTrue(hints["destructiveHint"], tool["name"])
                self.assertTrue(hints["openWorldHint"], tool["name"])
            else:
                self.assertTrue(hints["readOnlyHint"], tool["name"])
                self.assertFalse(hints["openWorldHint"], tool["name"])

    def test_every_input_schema_is_closed_and_described(self):
        for tool in self.tools:
            schema = tool["inputSchema"]
            self.assertIs(schema.get("additionalProperties"), False, tool["name"])
            for name, spec in schema["properties"].items():
                self.assertTrue(spec.get("description"), f"{tool['name']}.{name}")

    def test_names_fit_the_convention(self):
        import re
        for tool in self.tools:
            self.assertRegex(tool["name"], re.compile(r"^webrunner_[a-z0-9_]+$"))
            self.assertLessEqual(len(tool["name"]), 48, tool["name"])

    def test_browser_tools_declare_their_output(self):
        by_name = {tool["name"]: tool for tool in self.tools}
        for name in ("webrunner_run_actions", "webrunner_run_action_files"):
            self.assertEqual(by_name[name]["outputSchema"]["type"], "object", name)


class TestArgumentValidation(unittest.TestCase):
    """Bad arguments come back as tool errors the model can read and fix (MCP 2025-11-25, SEP-1303)."""

    def setUp(self):
        self.server = make_default_server()

    def _call(self, name, arguments):
        return self.server.handle({"id": 1, "method": "tools/call", "params": {
            "name": name, "arguments": arguments,
        }})["result"]

    def test_missing_required_argument(self):
        result = self._call("webrunner_partition_shard", {"paths": ["a"], "index": 1})
        self.assertTrue(result["isError"])
        self.assertIn("'total'", result["content"][0]["text"])

    def test_wrong_type(self):
        result = self._call("webrunner_partition_shard", {"paths": ["a"], "index": "x", "total": 2})
        self.assertTrue(result["isError"])
        self.assertIn("'index'", result["content"][0]["text"])

    def test_boolean_is_not_an_integer(self):
        result = self._call("webrunner_partition_shard", {"paths": ["a"], "index": True, "total": 2})
        self.assertTrue(result["isError"])

    def test_unknown_argument(self):
        result = self._call("webrunner_locator_strength", {"strategy": "ID", "value": "x", "extra": 1})
        self.assertTrue(result["isError"])
        self.assertIn("'extra'", result["content"][0]["text"])

    def test_null_optional_argument_counts_as_omitted(self):
        result = self._call("webrunner_summary_markdown",
                            {"total": 1, "passed": 1, "failed": 0, "run_url": None})
        self.assertFalse(result["isError"])


if __name__ == "__main__":
    unittest.main()
