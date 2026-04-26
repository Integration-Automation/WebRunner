import unittest

from je_web_runner.utils.exception.exceptions import WebRunnerExecuteException
from je_web_runner.utils.executor.action_executor import Executor


class TestArbitraryScriptGate(unittest.TestCase):

    def test_default_allows_arbitrary_script(self):
        executor = Executor()
        self.assertTrue(executor.allow_arbitrary_script)

    def test_disabled_blocks_execute_script(self):
        executor = Executor()
        executor.set_allow_arbitrary_script(False)
        executor.event_dict["WR_execute_script"] = lambda script: "ran"
        with self.assertRaises(WebRunnerExecuteException) as ctx:
            executor._execute_event(["WR_execute_script", {"script": "1+1"}])
        self.assertIn("disabled", str(ctx.exception))

    def test_disabled_blocks_pw_evaluate(self):
        executor = Executor()
        executor.set_allow_arbitrary_script(False)
        executor.event_dict["WR_pw_evaluate"] = lambda expression: 1
        with self.assertRaises(WebRunnerExecuteException):
            executor._execute_event(["WR_pw_evaluate", {"expression": "1"}])

    def test_disabled_blocks_cdp(self):
        executor = Executor()
        executor.set_allow_arbitrary_script(False)
        executor.event_dict["WR_cdp"] = lambda method: None
        with self.assertRaises(WebRunnerExecuteException):
            executor._execute_event(["WR_cdp", {"method": "Network.enable"}])

    def test_other_commands_still_run(self):
        executor = Executor()
        executor.set_allow_arbitrary_script(False)
        executor.event_dict["WR_safe"] = lambda: "ok"
        self.assertEqual(executor._execute_event(["WR_safe"]), "ok")

    def test_re_enable_restores_access(self):
        executor = Executor()
        executor.set_allow_arbitrary_script(False)
        executor.set_allow_arbitrary_script(True)
        executor.event_dict["WR_execute_script"] = lambda script: "ran"
        self.assertEqual(
            executor._execute_event(["WR_execute_script", {"script": "1+1"}]),
            "ran",
        )


if __name__ == "__main__":
    unittest.main()
