import os
import unittest
# defusedxml is required by CLAUDE.md for parsing untrusted XML.
from defusedxml.ElementTree import fromstring

from je_web_runner.utils.exception.exceptions import WebRunnerGenerateJsonReportException
from je_web_runner.utils.generate_report.generate_junit_xml_report import (
    generate_junit_xml,
    generate_junit_xml_report,
)
from je_web_runner.utils.test_record.test_record_class import (
    record_action_to_list,
    test_record_instance,
)


class TestJunitReport(unittest.TestCase):

    def setUp(self):
        test_record_instance.clean_record()
        self._original_init_record = test_record_instance.init_record
        test_record_instance.init_record = True

    def tearDown(self):
        test_record_instance.clean_record()
        test_record_instance.init_record = self._original_init_record
        for f in ["test_junit_junit.xml"]:
            if os.path.exists(f):
                os.remove(f)

    def test_generate_junit_xml_empty_raises(self):
        with self.assertRaises(WebRunnerGenerateJsonReportException):
            generate_junit_xml()

    def test_generate_junit_xml_counts_pass_and_fail(self):
        record_action_to_list("ok_func", None, None)
        record_action_to_list("bad_func", None, RuntimeError("boom"))
        record_action_to_list("ok_func2", None, None)
        xml_str = generate_junit_xml()
        root = fromstring(xml_str)
        self.assertEqual(root.tag, "testsuites")
        self.assertEqual(root.get("tests"), "3")
        self.assertEqual(root.get("failures"), "1")
        suite = root.find("testsuite")
        self.assertIsNotNone(suite)
        cases = suite.findall("testcase")
        self.assertEqual(len(cases), 3)
        failure_cases = [c for c in cases if c.find("failure") is not None]
        self.assertEqual(len(failure_cases), 1)
        self.assertIn("RuntimeError", failure_cases[0].find("failure").get("message"))

    def test_generate_junit_xml_report_writes_file(self):
        record_action_to_list("ok_func", {"p": 1}, None)
        generate_junit_xml_report("test_junit")
        self.assertTrue(os.path.exists("test_junit_junit.xml"))
        with open("test_junit_junit.xml", encoding="utf-8") as report_file:
            content = report_file.read()
        self.assertIn("<?xml", content)
        self.assertIn("testsuites", content)
        self.assertIn("ok_func", content)


if __name__ == "__main__":
    unittest.main()
