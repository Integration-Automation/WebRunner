import unittest

from je_web_runner.utils.executor.action_executor import Executor
from je_web_runner.utils.exception.exceptions import WebRunnerExecuteException


class TestExecutorMapping(unittest.TestCase):

    def setUp(self):
        self.executor = Executor()

    def test_event_dict_has_required_keys(self):
        required_keys = [
            "WR_get_webdriver_manager",
            "WR_set_driver",
            "WR_set_webdriver_options_capability",
            "WR_find_element",
            "WR_find_elements",
            "WR_to_url",
            "WR_quit",
            "WR_execute_action",
            "WR_execute_files",
            "WR_generate_html",
            "WR_generate_html_report",
            "WR_generate_json",
            "WR_generate_json_report",
            "WR_generate_xml",
            "WR_generate_xml_report",
            "WR_SaveTestObject",
            "WR_CleanTestObject",
            "WR_set_record_enable",
        ]
        for key in required_keys:
            self.assertIn(key, self.executor.event_dict, f"Missing key: {key}")

    def test_set_webdriver_options_capability_maps_correctly(self):
        from je_web_runner.webdriver.webdriver_wrapper import webdriver_wrapper_instance
        func = self.executor.event_dict["WR_set_webdriver_options_capability"]
        self.assertEqual(func, webdriver_wrapper_instance.set_webdriver_options_capability)

    def test_set_driver_maps_correctly(self):
        from je_web_runner.webdriver.webdriver_wrapper import webdriver_wrapper_instance
        func = self.executor.event_dict["WR_set_driver"]
        self.assertEqual(func, webdriver_wrapper_instance.set_driver)

    def test_set_driver_and_capability_are_different(self):
        func_driver = self.executor.event_dict["WR_set_driver"]
        func_cap = self.executor.event_dict["WR_set_webdriver_options_capability"]
        self.assertNotEqual(func_driver, func_cap)

    def test_execute_event_unknown_command_raises(self):
        with self.assertRaises(WebRunnerExecuteException):
            self.executor._execute_event(["NONEXISTENT_COMMAND_12345"])

    def test_execute_event_with_builtin(self):
        result = self.executor._execute_event(["print", ["hello"]])
        self.assertIsNone(result)

    def test_execute_event_invalid_format_raises(self):
        with self.assertRaises(WebRunnerExecuteException):
            self.executor._execute_event(["print", "arg1", "extra"])

    def test_execute_action_empty_list_raises(self):
        with self.assertRaises(WebRunnerExecuteException):
            self.executor.execute_action([])

    def test_execute_action_with_dict_missing_key_raises(self):
        with self.assertRaises(WebRunnerExecuteException):
            self.executor.execute_action({"wrong_key": []})

    def test_execute_action_with_builtins(self):
        actions = [
            ["print", ["test output"]],
        ]
        result = self.executor.execute_action(actions)
        self.assertIsInstance(result, dict)
        self.assertEqual(len(result), 1)


if __name__ == "__main__":
    unittest.main()
