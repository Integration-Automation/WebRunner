import json
import os
import tempfile
import unittest

from je_web_runner.utils.generate_report.report_manifest import (
    expected_paths,
    generate_all_reports,
)
from je_web_runner.utils.test_record.test_record_class import (
    record_action_to_list,
    test_record_instance,
)


class TestExpectedPaths(unittest.TestCase):

    def test_split_formats_have_two_paths(self):
        plan = expected_paths("run")
        self.assertEqual(plan["json"], ["run_success.json", "run_failure.json"])
        self.assertEqual(plan["xml"], ["run_success.xml", "run_failure.xml"])

    def test_single_file_formats(self):
        plan = expected_paths("run")
        self.assertEqual(plan["html"], ["run.html"])
        self.assertEqual(plan["junit"], ["run_junit.xml"])

    def test_allure_dir_optional(self):
        self.assertNotIn("allure", expected_paths("run"))
        self.assertEqual(expected_paths("run", allure_dir="out")["allure"], ["out"])


class TestGenerateAllReports(unittest.TestCase):

    def setUp(self):
        test_record_instance.clean_record()
        self._original = test_record_instance.init_record
        test_record_instance.init_record = True
        self._cwd = os.getcwd()
        self._tmpdir = tempfile.TemporaryDirectory()
        os.chdir(self._tmpdir.name)

    def tearDown(self):
        os.chdir(self._cwd)
        self._tmpdir.cleanup()
        test_record_instance.clean_record()
        test_record_instance.init_record = self._original

    def test_produced_lists_actual_files(self):
        record_action_to_list("ok", None, None)
        record_action_to_list("bad", None, RuntimeError("boom"))
        result = generate_all_reports("run")
        produced = result["produced"]
        # JSON / XML always emit both files; HTML and JUnit emit one.
        self.assertEqual(len(produced["json"]), 2)
        self.assertEqual(len(produced["xml"]), 2)
        self.assertEqual(len(produced["html"]), 1)
        self.assertEqual(len(produced["junit"]), 1)
        self.assertTrue(all(os.path.exists(path) for paths in produced.values() for path in paths))

    def test_manifest_is_written(self):
        record_action_to_list("ok", None, None)
        result = generate_all_reports("run")
        self.assertTrue(os.path.exists(result["manifest_path"]))
        with open(result["manifest_path"], encoding="utf-8") as manifest_file:
            payload = json.load(manifest_file)
        self.assertEqual(payload["base_name"], "run")
        self.assertIn("produced", payload)

    def test_no_records_collected_in_errors_not_raised(self):
        # No records → every generator raises; manifest still writes and the
        # function does not propagate the exceptions.
        result = generate_all_reports("run")
        self.assertGreater(len(result["errors"]), 0)
        self.assertTrue(os.path.exists(result["manifest_path"]))

    def test_write_manifest_can_be_disabled(self):
        record_action_to_list("ok", None, None)
        result = generate_all_reports("run", write_manifest=False)
        self.assertIsNone(result["manifest_path"])


if __name__ == "__main__":
    unittest.main()
