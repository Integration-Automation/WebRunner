"""
The AutoControl bridge against the real ``je_auto_control`` (skipped where it is not installed).

Nothing here moves the mouse or types: it reads AutoControl's command list and key table,
and runs an unknown command. The unit tests use a fake executor, so only this test sees
AutoControl rename what the bridge relies on (``architecture.md`` §6).
"""
import importlib.util
import unittest

from je_web_runner.utils.autocontrol_bridge import AutoControlBridgeError, ac_list_commands, ac_run
from je_web_runner.utils.executor.action_executor import executor

_USED_BY_WEBRUNNER = ("AC_write", "AC_type_keyboard", "AC_get_keyboard_keys_table",
                      "AC_locate_image_center", "AC_click_mouse", "AC_set_mouse_position")


@unittest.skipIf(importlib.util.find_spec("je_auto_control") is None, "je_auto_control is not installed")
class TestRealAutoControl(unittest.TestCase):

    def test_the_commands_webrunner_sends_exist_and_the_refused_ones_are_hidden(self):
        commands = set(ac_list_commands())
        self.assertLessEqual(set(_USED_BY_WEBRUNNER), commands)
        self.assertNotIn("AC_shell_command", commands)
        self.assertFalse(any(name.startswith("AC_web_") for name in commands))

    def test_run_through_the_action_executor(self):
        record, failed = executor.collect_action_results([["WR_ac_run", [["AC_get_keyboard_keys_table"]]]])
        self.assertEqual(failed, [])
        keys = next(iter(record.values()))
        self.assertIn("tab", keys)

    def test_the_key_table_names_enter(self):
        from je_web_runner.utils.autocontrol_bridge.native import _enter_key
        self.assertIn(_enter_key(), ("enter", "return"))

    def test_an_unknown_command_fails_as_a_bridge_error(self):
        with self.assertRaises(AutoControlBridgeError):
            ac_run(["AC_definitely_not_a_command"])


if __name__ == "__main__":
    unittest.main()
