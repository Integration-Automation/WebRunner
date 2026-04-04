import os
import shutil
import tempfile
import unittest

from je_web_runner.utils.project.create_project_structure import create_project_dir


class TestCreateProject(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_create_project_dir_creates_keyword_dir(self):
        create_project_dir(project_path=self.test_dir, parent_name="TestProject")
        keyword_path = os.path.join(self.test_dir, "TestProject", "keyword")
        self.assertTrue(os.path.isdir(keyword_path))

    def test_create_project_dir_creates_executor_dir(self):
        create_project_dir(project_path=self.test_dir, parent_name="TestProject")
        executor_path = os.path.join(self.test_dir, "TestProject", "executor")
        self.assertTrue(os.path.isdir(executor_path),
                        f"executor directory should exist at {executor_path}")

    def test_create_project_dir_no_merged_name(self):
        create_project_dir(project_path=self.test_dir, parent_name="WebRunner")
        bad_path = os.path.join(self.test_dir, "WebRunnerexecutor")
        self.assertFalse(os.path.exists(bad_path),
                         "Should not create merged directory 'WebRunnerexecutor'")

    def test_create_project_dir_creates_template_files(self):
        create_project_dir(project_path=self.test_dir, parent_name="TestProject")
        keyword_path = os.path.join(self.test_dir, "TestProject", "keyword")
        executor_path = os.path.join(self.test_dir, "TestProject", "executor")
        keyword_files = os.listdir(keyword_path) if os.path.isdir(keyword_path) else []
        executor_files = os.listdir(executor_path) if os.path.isdir(executor_path) else []
        self.assertTrue(len(keyword_files) > 0, "keyword dir should have template files")
        self.assertTrue(len(executor_files) > 0, "executor dir should have template files")


if __name__ == "__main__":
    unittest.main()
