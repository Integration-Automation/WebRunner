import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from je_web_runner.utils.accessibility.axe_audit import (
    AccessibilityError,
    load_axe_source,
    playwright_run_audit,
    selenium_run_audit,
    summarise_violations,
)


class TestLoadAxeSource(unittest.TestCase):

    def test_loads_existing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "axe.min.js")
            Path(path).write_text("// fake axe", encoding="utf-8")
            self.assertEqual(load_axe_source(path), "// fake axe")

    def test_missing_file_raises(self):
        with self.assertRaises(AccessibilityError):
            load_axe_source("/no/such/axe.js")


class TestSeleniumAudit(unittest.TestCase):

    def test_no_driver_raises(self):
        with patch(
            "je_web_runner.utils.accessibility.axe_audit.webdriver_wrapper_instance"
        ) as wrapper:
            wrapper.current_webdriver = None
            with self.assertRaises(AccessibilityError):
                selenium_run_audit("// axe")

    def test_runs_with_driver_returns_results(self):
        with patch(
            "je_web_runner.utils.accessibility.axe_audit.webdriver_wrapper_instance"
        ) as wrapper:
            driver = MagicMock()
            wrapper.current_webdriver = driver
            driver.execute_async_script.return_value = {
                "error": None,
                "results": {"violations": [{"id": "color-contrast"}]},
            }
            results = selenium_run_audit("// axe", options={"runOnly": ["wcag2a"]})
            self.assertEqual(results["violations"][0]["id"], "color-contrast")
            driver.execute_script.assert_called_once_with("// axe")
            driver.execute_async_script.assert_called_once()

    def test_axe_error_propagates(self):
        with patch(
            "je_web_runner.utils.accessibility.axe_audit.webdriver_wrapper_instance"
        ) as wrapper:
            driver = MagicMock()
            wrapper.current_webdriver = driver
            driver.execute_async_script.return_value = {"error": "boom", "results": None}
            with self.assertRaises(AccessibilityError):
                selenium_run_audit("// axe")


class TestPlaywrightAudit(unittest.TestCase):

    def test_runs_via_evaluate(self):
        with patch(
            "je_web_runner.utils.accessibility.axe_audit.playwright_wrapper_instance"
        ) as wrapper:
            page = MagicMock()
            wrapper.page = page
            page.evaluate.return_value = {"violations": []}
            results = playwright_run_audit("// axe", options={"reporter": "v2"})
            self.assertEqual(results, {"violations": []})
            page.add_script_tag.assert_called_once_with(content="// axe")
            self.assertEqual(page.evaluate.call_args[0][1], {"reporter": "v2"})


class TestSummarise(unittest.TestCase):

    def test_summary_compresses_violations(self):
        results = {
            "violations": [
                {
                    "id": "color-contrast",
                    "impact": "serious",
                    "help": "Elements must have sufficient contrast",
                    "nodes": [{}, {}, {}],
                },
                {
                    "id": "image-alt",
                    "impact": "critical",
                    "help": "Images must have alt text",
                    "nodes": [{}],
                },
            ]
        }
        summary = summarise_violations(results)
        self.assertEqual(len(summary), 2)
        self.assertEqual(summary[0]["nodes"], 3)
        self.assertEqual(summary[1]["impact"], "critical")

    def test_non_dict_input_returns_empty(self):
        self.assertEqual(summarise_violations(None), [])
        self.assertEqual(summarise_violations(["x"]), [])

    def test_missing_violations_key_returns_empty(self):
        self.assertEqual(summarise_violations({}), [])


if __name__ == "__main__":
    unittest.main()
