"""``execute_one``: one action through the executor's gates, raising instead of recording."""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from je_web_runner import execute_one as top_level_execute_one
from je_web_runner.utils.exception.exceptions import WebRunnerExecuteException
from je_web_runner.utils.executor import action_executor
from je_web_runner.utils.executor.action_executor import Executor


class TestExecuteOne(unittest.TestCase):

    def setUp(self):
        self.executor = Executor()
        self.command = MagicMock(return_value="done")
        self.executor.event_dict["WR_probe"] = self.command

    def test_returns_the_value_for_every_action_shape_and_prints_nothing(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(self.executor.execute_one(["WR_probe"]), "done")
            self.executor.execute_one(["WR_probe", {"a": 1}])
            self.executor.execute_one(["WR_probe", [2]])
            self.executor.execute_one(["WR_probe", [3], {"b": 4}])
        self.assertEqual(out.getvalue(), "")
        self.assertEqual([call.args for call in self.command.call_args_list], [(), (), (2,), (3,)])
        self.assertEqual(self.command.call_args_list[3].kwargs, {"b": 4})

    def test_a_failure_raises_with_its_cause(self):
        self.command.side_effect = ValueError("broken")
        with self.assertRaises(WebRunnerExecuteException) as caught:
            self.executor.execute_one(["WR_probe"])
        self.assertIsInstance(caught.exception.__cause__, ValueError)
        self.assertIn("broken", str(caught.exception))

    def test_malformed_and_unknown_actions_raise(self):
        for action in ([], "WR_probe", [5], None, ["WR_missing"]):
            with self.subTest(action=action), self.assertRaises(WebRunnerExecuteException):
                self.executor.execute_one(action)

    def test_refused_and_gated_commands_stay_refused(self):
        with self.executor.restricted({"WR_probe"}), self.assertRaises(WebRunnerExecuteException):
            self.executor.execute_one(["WR_probe"])
        self.executor.set_allow_arbitrary_script(False)
        self.executor.event_dict["WR_execute_script"] = MagicMock()
        with self.assertRaises(WebRunnerExecuteException):
            self.executor.execute_one(["WR_execute_script", {"script": "1"}])
        self.executor.event_dict["WR_execute_script"].assert_not_called()
        self.command.assert_not_called()

    def test_the_retry_policy_applies(self):
        self.command.side_effect = [RuntimeError("flaky"), "second"]
        self.executor.set_retry_policy(retries=1)
        self.assertEqual(self.executor.execute_one(["WR_probe"]), "second")

    def test_the_message_names_the_failure_screenshot(self):
        self.command.side_effect = RuntimeError("broken")
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(action_executor, "_try_selenium_screenshot", return_value=b"png"):
            self.executor.set_failure_screenshot_dir(tmp)
            with self.assertRaises(WebRunnerExecuteException) as caught:
                self.executor.execute_one(["WR_probe"])
            self.assertIn("failure screenshot", str(caught.exception))
            self.assertEqual(len(list(Path(tmp).glob("*_WR_probe.png"))), 1)

    def test_the_module_function_uses_the_global_executor(self):
        with patch.object(action_executor.executor, "execute_one", return_value=7) as method:
            self.assertEqual(top_level_execute_one(["WR_probe"]), 7)
        method.assert_called_once_with(["WR_probe"])


if __name__ == "__main__":
    unittest.main()
