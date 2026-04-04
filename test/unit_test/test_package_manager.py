import unittest

from je_web_runner.utils.package_manager.package_manager_class import PackageManager


class TestPackageManager(unittest.TestCase):

    def setUp(self):
        self.pm = PackageManager()

    def test_check_existing_package(self):
        result = self.pm.check_package("json")
        self.assertIsNotNone(result)

    def test_check_nonexistent_package(self):
        result = self.pm.check_package("nonexistent_package_xyz_123456")
        self.assertIsNone(result)

    def test_check_package_caches_result(self):
        self.pm.check_package("os")
        self.assertIn("os", self.pm.installed_package_dict)
        first = self.pm.installed_package_dict["os"]
        self.pm.check_package("os")
        self.assertIs(self.pm.installed_package_dict["os"], first)

    def test_add_package_to_executor_with_mock(self):
        class MockExecutor:
            def __init__(self):
                self.event_dict = {}

        self.pm.executor = MockExecutor()
        self.pm.add_package_to_executor("json")
        self.assertTrue(len(self.pm.executor.event_dict) > 0)

    def test_add_package_to_callback_executor_with_mock(self):
        class MockExecutor:
            def __init__(self):
                self.event_dict = {}

        self.pm.callback_executor = MockExecutor()
        self.pm.add_package_to_callback_executor("os")
        self.assertTrue(len(self.pm.callback_executor.event_dict) > 0)


if __name__ == "__main__":
    unittest.main()
