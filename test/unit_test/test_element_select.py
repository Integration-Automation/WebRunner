import unittest
from typing import Any
from unittest.mock import MagicMock, patch

from je_web_runner.element.web_element_wrapper import WebElementWrapper
from je_web_runner.utils.executor.action_executor import executor


class TestWebElementSelectMethods(unittest.TestCase):

    def test_select_by_value_invokes_select_helper(self):
        wrapper = WebElementWrapper()
        wrapper.current_web_element = MagicMock()
        with patch("je_web_runner.element.web_element_wrapper.Select") as select_cls:
            wrapper.select_by_value("opt-1")
            select_cls.assert_called_once_with(wrapper.current_web_element)
            select_cls.return_value.select_by_value.assert_called_once_with("opt-1")

    def test_select_by_index_casts_to_int(self):
        wrapper = WebElementWrapper()
        wrapper.current_web_element = MagicMock()
        with patch("je_web_runner.element.web_element_wrapper.Select") as select_cls:
            # The implementation runs ``int(index)`` so a string is the
            # exact case we want to exercise. Pass it through ``Any`` to
            # keep static analysers (SonarCloud S5655) from over-checking
            # the test fixture.
            string_index: Any = "3"
            wrapper.select_by_index(string_index)  # NOSONAR — fixture exercises the str→int cast
            select_cls.return_value.select_by_index.assert_called_once_with(3)

    def test_select_by_visible_text_invokes_select_helper(self):
        wrapper = WebElementWrapper()
        wrapper.current_web_element = MagicMock()
        with patch("je_web_runner.element.web_element_wrapper.Select") as select_cls:
            wrapper.select_by_visible_text("Taiwan")
            select_cls.return_value.select_by_visible_text.assert_called_once_with("Taiwan")

    def test_failure_does_not_raise(self):
        wrapper = WebElementWrapper()
        wrapper.current_web_element = MagicMock()
        with patch("je_web_runner.element.web_element_wrapper.Select") as select_cls:
            select_cls.return_value.select_by_value.side_effect = RuntimeError("boom")
            # Mirrors the existing element-wrapper convention: failures are
            # logged and recorded, not re-raised.
            wrapper.select_by_value("missing")


class TestExecutorWiring(unittest.TestCase):

    def test_select_commands_present(self):
        for command in (
            "WR_element_select_by_value",
            "WR_element_select_by_index",
            "WR_element_select_by_visible_text",
        ):
            self.assertIn(command, executor.event_dict)
            self.assertTrue(callable(executor.event_dict[command]))


if __name__ == "__main__":
    unittest.main()
