import json
import os
import unittest

from je_web_runner.utils.exception.exceptions import (
    WebRunnerGenerateJsonReportException,
    WebRunnerHTMLException,
)
from je_web_runner.utils.generate_report.generate_html_report import generate_html
from je_web_runner.utils.generate_report.generate_json_report import generate_json, generate_json_report
from je_web_runner.utils.test_record.test_record_class import test_record_instance, record_action_to_list


class TestReportGeneration(unittest.TestCase):

    def setUp(self):
        test_record_instance.clean_record()
        self._original_init_record = test_record_instance.init_record
        test_record_instance.init_record = True

    def tearDown(self):
        test_record_instance.clean_record()
        test_record_instance.init_record = self._original_init_record
        for f in ["test_report_success.json", "test_report_failure.json"]:
            if os.path.exists(f):
                os.remove(f)

    def test_generate_json_empty_records_raises(self):
        test_record_instance.clean_record()
        with self.assertRaises(WebRunnerGenerateJsonReportException):
            generate_json()

    def test_generate_html_empty_records_raises(self):
        test_record_instance.clean_record()
        with self.assertRaises(WebRunnerHTMLException):
            generate_html()

    def test_generate_json_success_records(self):
        record_action_to_list("test_func", {"key": "val"}, None)
        success_dict, failure_dict = generate_json()
        self.assertEqual(len(success_dict), 1)
        self.assertEqual(len(failure_dict), 0)
        entry = success_dict["Success_Test1"]
        self.assertEqual(entry["function_name"], "test_func")

    def test_generate_json_failure_records(self):
        record_action_to_list("fail_func", {"key": "val"}, ValueError("err"))
        success_dict, failure_dict = generate_json()
        self.assertEqual(len(success_dict), 0)
        self.assertEqual(len(failure_dict), 1)
        entry = failure_dict["Failure_Test1"]
        self.assertEqual(entry["function_name"], "fail_func")
        self.assertIn("ValueError", entry["exception"])

    def test_generate_json_mixed_records(self):
        record_action_to_list("ok_func", None, None)
        record_action_to_list("err_func", None, RuntimeError("boom"))
        record_action_to_list("ok_func2", None, None)
        success_dict, failure_dict = generate_json()
        self.assertEqual(len(success_dict), 2)
        self.assertEqual(len(failure_dict), 1)

    def test_generate_json_report_creates_files(self):
        record_action_to_list("func", {"p": 1}, None)
        record_action_to_list("func2", {"p": 2}, RuntimeError("err"))
        generate_json_report("test_report")
        self.assertTrue(os.path.exists("test_report_success.json"))
        self.assertTrue(os.path.exists("test_report_failure.json"))
        with open("test_report_success.json") as f:
            data = json.load(f)
            self.assertIn("Success_Test1", data)
        with open("test_report_failure.json") as f:
            data = json.load(f)
            self.assertIn("Failure_Test1", data)

    def test_generate_html_contains_report_structure(self):
        record_action_to_list("html_func", {"a": 1}, None)
        html = generate_html()
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("Test Report", html)
        self.assertIn("html_func", html)
        self.assertIn("event_table_head", html)

    def test_generate_html_failure_uses_failure_class(self):
        record_action_to_list("err_func", None, RuntimeError("err"))
        html = generate_html()
        self.assertIn("failure_table_head", html)


if __name__ == "__main__":
    unittest.main()
