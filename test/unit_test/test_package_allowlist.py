"""The package gate in front of WR_add_package_to_executor (progress #11, workspace X-12)."""
import types
import unittest
import warnings
from unittest.mock import patch

from je_web_runner.utils.exception.exceptions import WebRunnerExecuteException
from je_web_runner.utils.executor.action_executor import executor
from je_web_runner.utils.package_manager import package_manager_class
from je_web_runner.utils.package_manager.package_manager_class import PackageManager


def _manager():
    manager = PackageManager()
    manager.executor = types.SimpleNamespace(event_dict={})
    return manager


class TestPackageGate(unittest.TestCase):

    def test_unconfigured_gate_still_loads_but_warns(self):
        manager = _manager()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            manager.add_package_to_executor("json")
        self.assertIn("json_dumps", manager.executor.event_dict)
        self.assertTrue(any(issubclass(w.category, DeprecationWarning) for w in caught))

    def test_closed_gate_refuses_before_importing(self):
        manager = _manager()
        manager.set_allow_arbitrary_packages(False)
        with patch.object(package_manager_class, "import_module") as importer:
            with self.assertRaises(WebRunnerExecuteException):
                manager.add_package_to_executor("os")
            importer.assert_not_called()
        self.assertEqual(manager.executor.event_dict, {})

    def test_closed_gate_refuses_the_callback_executor_too(self):
        manager = PackageManager()
        manager.callback_executor = types.SimpleNamespace(event_dict={})
        manager.set_allow_arbitrary_packages(False)
        with self.assertRaises(WebRunnerExecuteException):
            manager.add_package_to_callback_executor("subprocess")

    def test_allowlisted_package_and_its_submodules_load_without_warning(self):
        manager = _manager()
        manager.set_allow_arbitrary_packages(False)
        manager.allow_packages("json")
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            manager.add_package_to_executor("json")
            manager.add_package_to_executor("json.decoder")
        self.assertIn("json_dumps", manager.executor.event_dict)
        with self.assertRaises(WebRunnerExecuteException):
            manager.add_package_to_executor("jsonschema_lookalike")

    def test_open_gate_loads_anything_without_warning(self):
        manager = _manager()
        manager.set_allow_arbitrary_packages(True)
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            manager.add_package_to_executor("json")
        self.assertIn("json_dumps", manager.executor.event_dict)


class TestExecutorSwitches(unittest.TestCase):

    def setUp(self):
        manager = package_manager_class.package_manager
        saved = (manager.allow_arbitrary_packages, set(manager.allowed_packages))

        def restore():
            manager.allow_arbitrary_packages, manager.allowed_packages = saved[0], set(saved[1])
        self.addCleanup(restore)

    def test_executor_configures_the_shared_gate(self):
        executor.set_allow_arbitrary_packages(False)
        executor.allow_packages("my_company_helpers")
        manager = package_manager_class.package_manager
        self.assertIs(manager.allow_arbitrary_packages, False)
        self.assertIn("my_company_helpers", manager.allowed_packages)

    def test_no_action_command_can_open_the_gate(self):
        for name in executor.event_dict:
            self.assertNotIn("allow_arbitrary_packages", name)
            self.assertNotIn("allow_packages", name)

    def test_refusal_reaches_the_action_record(self):
        executor.set_allow_arbitrary_packages(False)
        record, failed = executor.collect_action_results([["WR_add_package_to_executor", {"package": "os"}]])
        self.assertEqual(len(failed), 1)
        self.assertIn("not allowed", record[failed[0]])


if __name__ == "__main__":
    unittest.main()
