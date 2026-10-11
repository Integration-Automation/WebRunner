"""MCP callers cannot load packages or re-open the script gate, and file tools can be fenced to a root."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from je_web_runner.mcp_server.server import make_default_server
from je_web_runner.utils.executor.action_executor import executor


class TestRestrictedExecutor(unittest.TestCase):

    def test_denied_command_fails_inside_and_works_after(self):
        with executor.restricted({"WR_sleep"}):
            _record, failed = executor.collect_action_results([["WR_sleep", {"seconds": 0}]])
        self.assertEqual(len(failed), 1)
        _record, failed = executor.collect_action_results([["WR_sleep", {"seconds": 0}]])
        self.assertEqual(failed, [])

    def test_nested_action_lists_are_restricted_too(self):
        with executor.restricted({"WR_sleep"}):
            record, _failed = executor.collect_action_results(
                [["WR_execute_action", {"action_list": [["WR_sleep", {"seconds": 0}]]}]])
        self.assertIn("not allowed", json.dumps(record, default=str))


class TestMcpPolicy(unittest.TestCase):

    def setUp(self):
        self.server = make_default_server()

    def _call(self, name, arguments):
        return self.server.handle({"id": 1, "method": "tools/call", "params": {
            "name": name, "arguments": arguments,
        }})["result"]

    def test_package_loading_is_refused_by_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("WEBRUNNER_MCP_ALLOW_UNSAFE_COMMANDS", None)
            result = self._call("webrunner_run_actions",
                                {"actions": [["WR_add_package_to_executor", {"package": "os"}]]})
        self.assertTrue(result["isError"])
        self.assertNotIn("os_system", executor.event_dict)

    def test_script_gate_cannot_be_reopened(self):
        original = executor.allow_arbitrary_script
        self.addCleanup(executor.set_allow_arbitrary_script, original)
        executor.set_allow_arbitrary_script(False)
        os.environ.pop("WEBRUNNER_MCP_ALLOW_UNSAFE_COMMANDS", None)
        result = self._call("webrunner_run_actions",
                            {"actions": [["WR_set_allow_arbitrary_script", {"enabled": True}]]})
        self.assertTrue(result["isError"])
        self.assertFalse(executor.allow_arbitrary_script)

    def test_operator_can_lift_the_policy(self):
        original = executor.allow_arbitrary_script
        self.addCleanup(executor.set_allow_arbitrary_script, original)
        with patch.dict(os.environ, {"WEBRUNNER_MCP_ALLOW_UNSAFE_COMMANDS": "1"}):
            result = self._call("webrunner_run_actions",
                                {"actions": [["WR_set_allow_arbitrary_script", {"enabled": True}]]})
        self.assertFalse(result["isError"])


class TestMcpFileRoot(unittest.TestCase):

    def setUp(self):
        self.server = make_default_server()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "allowed"
        self.root.mkdir()

    def _call(self, name, arguments):
        return self.server.handle({"id": 1, "method": "tools/call", "params": {
            "name": name, "arguments": arguments,
        }})["result"]

    def test_files_outside_the_root_are_refused(self):
        outside = Path(self.tmp.name) / "outside.json"
        outside.write_text("[]", encoding="utf-8")
        with patch.dict(os.environ, {"WEBRUNNER_MCP_ROOT": str(self.root)}):
            run = self._call("webrunner_run_action_files", {"files": [str(outside)]})
            trend = self._call("webrunner_compute_trend", {"ledger_path": str(outside)})
            escape = self._call("webrunner_run_action_files",
                                {"files": [str(self.root / ".." / "outside.json")]})
        for result in (run, trend, escape):
            self.assertTrue(result["isError"])
            self.assertIn("WEBRUNNER_MCP_ROOT", result["content"][0]["text"])

    def test_files_inside_the_root_run(self):
        inside = self.root / "steps.json"
        inside.write_text(json.dumps([["WR_sleep", {"seconds": 0}]]), encoding="utf-8")
        with patch.dict(os.environ, {"WEBRUNNER_MCP_ROOT": str(self.root)}):
            result = self._call("webrunner_run_action_files", {"files": [str(inside)]})
        self.assertFalse(result["isError"])


if __name__ == "__main__":
    unittest.main()
