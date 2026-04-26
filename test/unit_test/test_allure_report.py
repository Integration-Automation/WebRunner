import json
import os
import tempfile
import unittest

from je_web_runner.utils.exception.exceptions import WebRunnerGenerateJsonReportException
from je_web_runner.utils.generate_report.generate_allure_report import (
    generate_allure,
    generate_allure_report,
)
from je_web_runner.utils.test_record.test_record_class import (
    record_action_to_list,
    test_record_instance,
)


class TestAllureReport(unittest.TestCase):

    def setUp(self):
        test_record_instance.clean_record()
        self._original = test_record_instance.init_record
        test_record_instance.init_record = True

    def tearDown(self):
        test_record_instance.clean_record()
        test_record_instance.init_record = self._original

    def test_no_records_raises(self):
        with self.assertRaises(WebRunnerGenerateJsonReportException):
            generate_allure()

    def test_passes_only_yields_passed_case(self):
        record_action_to_list("WR_to_url", {"url": "x"}, None)
        record_action_to_list("WR_quit", None, None)
        cases = generate_allure()
        self.assertEqual(len(cases), 1)
        case = cases[0]
        self.assertEqual(case["status"], "passed")
        self.assertEqual(len(case["steps"]), 2)
        self.assertTrue(all(step["status"] == "passed" for step in case["steps"]))

    def test_failure_marks_case_and_step_failed(self):
        record_action_to_list("WR_to_url", {"url": "x"}, None)
        record_action_to_list("WR_quit", None, RuntimeError("boom"))
        case = generate_allure()[0]
        self.assertEqual(case["status"], "failed")
        statuses = [step["status"] for step in case["steps"]]
        self.assertEqual(statuses, ["passed", "failed"])
        self.assertIn("RuntimeError", case["steps"][1]["statusDetails"]["message"])

    def test_generate_allure_report_writes_files(self):
        record_action_to_list("WR_to_url", {"url": "x"}, None)
        with tempfile.TemporaryDirectory() as tmpdir:
            written = generate_allure_report(tmpdir)
            self.assertEqual(len(written), 1)
            self.assertTrue(os.path.exists(written[0]))
            self.assertTrue(written[0].endswith("-result.json"))
            with open(written[0], encoding="utf-8") as result_file:
                payload = json.load(result_file)
            self.assertEqual(payload["status"], "passed")
            self.assertEqual(payload["labels"][0]["value"], "webrunner")


if __name__ == "__main__":
    unittest.main()
