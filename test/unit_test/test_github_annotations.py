import io
import os
import tempfile
import unittest
from pathlib import Path

from je_web_runner.utils.ci_annotations.github_annotations import (
    AnnotationError,
    emit_failure_annotations,
    emit_from_junit_xml,
    format_error_annotation,
)
from je_web_runner.utils.test_record.test_record_class import (
    record_action_to_list,
    test_record_instance,
)


class TestFormatAnnotation(unittest.TestCase):

    def test_minimal_annotation(self):
        line = format_error_annotation("boom")
        self.assertEqual(line, "::error::boom")

    def test_with_file_and_title(self):
        line = format_error_annotation("boom", file="actions/login.json", title="step1")
        self.assertIn("file=actions/login.json", line)
        self.assertIn("title=step1", line)

    def test_escapes_newlines_and_percent(self):
        line = format_error_annotation("100%\nnext line")
        self.assertIn("100%25", line)
        self.assertIn("%0A", line)


class TestEmitFailures(unittest.TestCase):

    def setUp(self):
        test_record_instance.clean_record()
        self._original = test_record_instance.init_record
        test_record_instance.init_record = True

    def tearDown(self):
        test_record_instance.clean_record()
        test_record_instance.init_record = self._original

    def test_emits_one_line_per_failure(self):
        record_action_to_list("step_ok", None, None)
        record_action_to_list("step_fail", None, RuntimeError("boom"))
        record_action_to_list("step_fail2", None, ValueError("nope"))
        stream = io.StringIO()
        lines = emit_failure_annotations(stream=stream)
        self.assertEqual(len(lines), 2)
        output = stream.getvalue()
        self.assertEqual(output.count("::error"), 2)
        self.assertIn("step_fail", output)
        self.assertIn("step_fail2", output)

    def test_no_failures_yields_no_lines(self):
        record_action_to_list("step_ok", None, None)
        stream = io.StringIO()
        self.assertEqual(emit_failure_annotations(stream=stream), [])
        self.assertEqual(stream.getvalue(), "")


class TestEmitFromJunit(unittest.TestCase):

    def test_emits_for_each_failure(self):
        xml = """<?xml version="1.0"?>
<testsuites>
  <testsuite name="suite">
    <testcase name="login" classname="auth.login" />
    <testcase name="logout" classname="auth.logout">
      <failure message="WebRunnerExecutionError">trace</failure>
    </testcase>
    <testcase name="checkout" classname="commerce.checkout">
      <failure message="other">trace</failure>
    </testcase>
  </testsuite>
</testsuites>"""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "junit.xml")
            Path(path).write_text(xml, encoding="utf-8")
            stream = io.StringIO()
            lines = emit_from_junit_xml(path, stream=stream)
            self.assertEqual(len(lines), 2)
            self.assertIn("logout", stream.getvalue())
            self.assertIn("checkout", stream.getvalue())

    def test_missing_file_raises(self):
        with self.assertRaises(AnnotationError):
            emit_from_junit_xml("/no/such/path.xml")

    def test_invalid_xml_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "junit.xml")
            Path(path).write_text("<not-xml", encoding="utf-8")
            with self.assertRaises(AnnotationError):
                emit_from_junit_xml(path)


if __name__ == "__main__":
    unittest.main()
