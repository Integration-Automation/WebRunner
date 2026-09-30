"""The AutoControl bridge (``WR_ac_*``) against a fake AutoControl executor."""
import json
import os
import subprocess  # nosec B404 — runs this interpreter on a fixed snippet
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from je_web_runner.mcp_server import _policy
from je_web_runner.utils.autocontrol_bridge import bridge
from je_web_runner.utils.autocontrol_bridge.bridge import (
    AutoControlBridgeError,
    ac_available,
    ac_list_commands,
    ac_run,
    ac_run_actions,
)
from je_web_runner.utils.executor.action_executor import executor

_REPO_ROOT = Path(bridge.__file__).resolve().parents[3]


def _fake_ac(record=None, error=None):
    fake = MagicMock()
    fake.known_commands.return_value = {"AC_write", "AC_click_mouse", "AC_shell_command",
                                        "AC_web_run", "AC_add_package_to_executor", "AC_loop"}
    if error is not None:
        fake.execute_action.side_effect = error
    else:
        fake.execute_action.side_effect = lambda actions, raise_on_error: record or {
            f"execute: {action}": f"ran {action[0]}" for action in actions}
    return fake


class TestAvailability(unittest.TestCase):

    def test_looks_the_package_up_without_importing_it(self):
        with patch("importlib.util.find_spec", return_value=object()) as find_spec:
            self.assertTrue(ac_available())
        find_spec.assert_called_once_with("je_auto_control")
        with patch("importlib.util.find_spec", return_value=None):
            self.assertFalse(ac_available())
        with patch("importlib.util.find_spec", side_effect=ValueError("half imported")):
            self.assertFalse(ac_available())

    def test_missing_autocontrol_says_how_to_install_it(self):
        with patch.object(bridge, "ac_available", return_value=False), \
                self.assertRaisesRegex(AutoControlBridgeError, r"je_web_runner\[autocontrol\]"):
            ac_run(["AC_write", {"write_string": "x"}])

    def test_importing_webrunner_does_not_import_autocontrol(self):
        snippet = "import sys, je_web_runner; print('je_auto_control' in sys.modules)"
        with tempfile.TemporaryDirectory() as cwd:  # the import writes WEBRunner.log into the cwd
            result = subprocess.run([sys.executable, "-c", snippet], cwd=cwd, capture_output=True,  # nosec B603
                                    text=True, timeout=120, check=True,
                                    env={**os.environ, "PYTHONPATH": str(_REPO_ROOT)})
        self.assertEqual(result.stdout.strip().splitlines()[-1], "False")


class TestRunning(unittest.TestCase):

    def setUp(self):
        self.fake = _fake_ac()
        patcher = patch.object(bridge, "ac_executor", return_value=self.fake)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_run_one_and_many(self):
        self.assertEqual(ac_run(["AC_write", {"write_string": "hi"}]), "ran AC_write")
        self.fake.execute_action.assert_called_with([["AC_write", {"write_string": "hi"}]], raise_on_error=True)
        self.assertEqual(ac_run_actions([["AC_write", {"write_string": "a"}], ["AC_click_mouse"]]),
                         ["ran AC_write", "ran AC_click_mouse"])

    def test_list_leaves_out_refused_commands(self):
        self.assertEqual(ac_list_commands(), ["AC_click_mouse", "AC_loop", "AC_write"])

    def test_malformed_actions_are_rejected(self):
        for action in ([], "AC_write", [5], ["WR_to_url"], None):
            with self.subTest(action=action), self.assertRaises(AutoControlBridgeError):
                ac_run(action)
        with self.assertRaises(AutoControlBridgeError):
            ac_run_actions([])
        self.fake.execute_action.assert_not_called()

    def test_refused_commands_are_refused_wherever_they_appear(self):
        refused = (
            ["AC_shell_command", {"shell_command": "calc"}],
            ["AC_add_package_to_executor", {"package": "os"}],
            ["AC_loop", {"times": 2, "body": [["AC_execute_process", {"exe_path": "x"}]]}],
            ["AC_loop", {"times": 1, "body": json.dumps([["AC_web_run", {"action": "WR_quit"}]])}],
            ["AC_write", {"AC_execute_action": 1}],
            ["AC_run_agent", {"goal": "anything"}],
        )
        for action in refused:
            with self.subTest(action=action), self.assertRaisesRegex(AutoControlBridgeError, "refused"):
                ac_run(action)
        self.fake.execute_action.assert_not_called()

    def test_an_autocontrol_failure_is_wrapped_with_its_cause(self):
        error = RuntimeError("image not found")
        self.fake.execute_action.side_effect = error
        with self.assertRaises(AutoControlBridgeError) as caught:
            ac_run(["AC_locate_image_center", {"image": "x.png"}])
        self.assertIs(caught.exception.__cause__, error)


class TestCommands(unittest.TestCase):

    def test_registered_and_denied_over_mcp_by_default(self):
        for name in ("WR_ac_available", "WR_ac_list_commands", "WR_ac_run", "WR_ac_run_actions"):
            self.assertIn(name, executor.event_dict)
        with patch.dict("os.environ", {_policy.ALLOW_UNSAFE_ENV: ""}):
            denied = _policy.denied_commands()
        self.assertIn("WR_ac_run", denied)
        self.assertIn("WR_ac_run_actions", denied)
        self.assertNotIn("WR_ac_available", denied)


if __name__ == "__main__":
    unittest.main()
