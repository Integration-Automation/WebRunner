import unittest

from je_web_runner.utils.callback.callback_function_executor import callback_executor
from je_web_runner.utils.executor.action_executor import executor


_LEGACY_TO_ALIAS = [
    ("WR_get_webdriver_manager", "WR_new_driver"),
    ("WR_quit", "WR_quit_all"),
    ("WR_single_quit", "WR_quit_current"),
    ("WR_explict_wait", "WR_explicit_wait"),
    ("WR_SaveTestObject", "WR_save_test_object"),
    ("WR_CleanTestObject", "WR_clear_test_objects"),
    ("WR_find_element", "WR_find_recorded_element"),
    ("WR_find_elements", "WR_find_recorded_elements"),
    ("WR_input_to_element", "WR_element_input"),
    ("WR_click_element", "WR_element_click"),
    ("WR_element_check_current_web_element", "WR_element_assert"),
]


class TestActionExecutorAliases(unittest.TestCase):

    def test_legacy_and_alias_resolve_to_same_callable(self):
        for legacy, alias in _LEGACY_TO_ALIAS:
            with self.subTest(pair=(legacy, alias)):
                self.assertIn(legacy, executor.event_dict)
                self.assertIn(alias, executor.event_dict)
                # Bound methods are re-created on each attribute access,
                # so identity (``is``) is too strict. Equality works because
                # bound methods compare equal when wrapping the same
                # instance and function.
                self.assertEqual(
                    executor.event_dict[legacy],
                    executor.event_dict[alias],
                    msg=f"{alias!r} should reference the same callable as {legacy!r}",
                )


class TestCallbackExecutorAliases(unittest.TestCase):

    def test_callback_executor_has_same_aliases(self):
        for legacy, alias in _LEGACY_TO_ALIAS:
            with self.subTest(pair=(legacy, alias)):
                self.assertIn(alias, callback_executor.event_dict)
                self.assertEqual(
                    callback_executor.event_dict[legacy],
                    callback_executor.event_dict[alias],
                )


if __name__ == "__main__":
    unittest.main()
