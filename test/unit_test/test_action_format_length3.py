import unittest

from je_web_runner.utils.exception.exceptions import WebRunnerExecuteException
from je_web_runner.utils.executor.action_executor import Executor
from je_web_runner.utils.json.json_validator import validate_action_json


class TestExecutorLength3Action(unittest.TestCase):

    def test_mixed_positional_and_kwargs_dispatched(self):
        executor = Executor()

        def target(a, b, *, multiplier=1):
            return (a + b) * multiplier

        executor.event_dict["WR_test_mixed"] = target
        result = executor._execute_event(["WR_test_mixed", [2, 3], {"multiplier": 4}])
        self.assertEqual(result, 20)

    def test_length3_rejects_dict_in_slot1(self):
        executor = Executor()
        executor.event_dict["WR_test"] = lambda: None
        with self.assertRaises(WebRunnerExecuteException):
            executor._execute_event(["WR_test", {"a": 1}, {"b": 2}])

    def test_length3_rejects_list_in_slot2(self):
        executor = Executor()
        executor.event_dict["WR_test"] = lambda: None
        with self.assertRaises(WebRunnerExecuteException):
            executor._execute_event(["WR_test", [1, 2], [3, 4]])

    def test_length4_still_invalid(self):
        executor = Executor()
        executor.event_dict["WR_test"] = lambda: None
        with self.assertRaises(WebRunnerExecuteException):
            executor._execute_event(["WR_test", [1], {"a": 1}, "extra"])

    def test_existing_length1_and_length2_still_work(self):
        executor = Executor()
        captured = {}

        def target(value="default"):
            captured["value"] = value

        executor.event_dict["WR_test"] = target
        executor._execute_event(["WR_test"])
        self.assertEqual(captured["value"], "default")
        executor._execute_event(["WR_test", {"value": "kw"}])
        self.assertEqual(captured["value"], "kw")
        executor._execute_event(["WR_test", ["positional"]])
        self.assertEqual(captured["value"], "positional")


class TestValidatorLength3(unittest.TestCase):

    def test_valid_length3_action(self):
        self.assertTrue(validate_action_json([
            ["WR_to_url", ["https://e.com"], {"timeout": 30}],
        ]))

    def test_length3_requires_list_first(self):
        with self.assertRaises(WebRunnerExecuteException):
            validate_action_json([["WR_x", {"a": 1}, {"b": 2}]])

    def test_length3_requires_dict_second(self):
        with self.assertRaises(WebRunnerExecuteException):
            validate_action_json([["WR_x", [1], [2]]])

    def test_length4_rejected(self):
        with self.assertRaises(WebRunnerExecuteException):
            validate_action_json([["WR_x", [1], {"a": 1}, "extra"]])


if __name__ == "__main__":
    unittest.main()
