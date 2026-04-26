import json
import unittest
from unittest.mock import MagicMock

from je_web_runner.utils.csp_reporter import (
    CspReporterError,
    CspViolationCollector,
)
from je_web_runner.utils.csp_reporter.reporter import (
    assert_no_violations,
)


class TestCspViolationCollector(unittest.TestCase):

    def test_install_via_execute_script(self):
        driver = MagicMock()
        collector = CspViolationCollector()
        collector.install(driver)
        driver.execute_script.assert_called_once()

    def test_install_unsupported_driver_raises(self):
        with self.assertRaises(CspReporterError):
            CspViolationCollector().install(object())

    def test_collect_parses_payload(self):
        driver = MagicMock()
        driver.execute_script.return_value = json.dumps([
            {
                "violatedDirective": "script-src",
                "blockedURI": "inline",
                "sourceFile": "page.js",
                "lineNumber": 42,
                "sample": "alert(1)",
            }
        ])
        collector = CspViolationCollector()
        violations = collector.collect(driver)
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0].violated_directive, "script-src")
        self.assertEqual(violations[0].line_number, 42)

    def test_assert_none_raises(self):
        driver = MagicMock()
        driver.execute_script.return_value = json.dumps([
            {"violatedDirective": "img-src", "blockedURI": "http://evil"},
        ])
        collector = CspViolationCollector()
        collector.collect(driver)
        with self.assertRaises(CspReporterError):
            collector.assert_none()

    def test_assert_no_directive_passes_when_other(self):
        driver = MagicMock()
        driver.execute_script.return_value = json.dumps([
            {"violatedDirective": "img-src", "blockedURI": "x"},
        ])
        collector = CspViolationCollector()
        collector.collect(driver)
        collector.assert_no_directive("script-src")
        with self.assertRaises(CspReporterError):
            collector.assert_no_directive("img-src")


class TestAllowList(unittest.TestCase):

    def test_allow_list_filters(self):
        driver = MagicMock()
        driver.execute_script.return_value = json.dumps([
            {"violatedDirective": "report-only", "blockedURI": "x"},
        ])
        # Allow list lets the only violation through cleanly
        assert_no_violations(driver, allow_directives=["report-only"])


if __name__ == "__main__":
    unittest.main()
