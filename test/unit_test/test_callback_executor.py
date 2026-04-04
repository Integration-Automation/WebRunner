import unittest

from je_web_runner.utils.callback.callback_function_executor import CallbackFunctionExecutor


class TestCallbackExecutorMapping(unittest.TestCase):

    def setUp(self):
        self.executor = CallbackFunctionExecutor()

    def test_event_dict_has_required_keys(self):
        required_keys = [
            "WR_get_webdriver_manager",
            "WR_set_driver",
            "WR_set_webdriver_options_capability",
            "WR_find_element",
            "WR_quit",
            "WR_execute_action",
            "WR_execute_files",
        ]
        for key in required_keys:
            self.assertIn(key, self.executor.event_dict, f"Missing key: {key}")

    def test_set_webdriver_options_capability_maps_correctly(self):
        from je_web_runner.webdriver.webdriver_wrapper import webdriver_wrapper_instance
        func = self.executor.event_dict["WR_set_webdriver_options_capability"]
        self.assertEqual(func, webdriver_wrapper_instance.set_webdriver_options_capability)

    def test_set_driver_and_capability_are_different(self):
        func_driver = self.executor.event_dict["WR_set_driver"]
        func_cap = self.executor.event_dict["WR_set_webdriver_options_capability"]
        self.assertNotEqual(func_driver, func_cap)

    def test_callback_with_invalid_trigger_returns_none(self):
        result = self.executor.callback_function(
            trigger_function_name="NONEXISTENT",
            callback_function=print,
        )
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
