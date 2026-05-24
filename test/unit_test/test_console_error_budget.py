"""Unit tests for je_web_runner.utils.console_error_budget."""
import re
import unittest

from je_web_runner.utils.console_error_budget.budget import (
    BudgetReport,
    ConsoleBudgetError,
    ConsoleMessage,
    ErrorBudget,
    evaluate,
    from_cdp_console_events,
    from_cdp_exception_events,
    from_selenium_log,
)


class TestConsoleMessage(unittest.TestCase):

    def test_normalises_warn_to_warning(self):
        self.assertEqual(ConsoleMessage(severity="warn", text="x").severity, "warning")

    def test_normalises_severe_to_error(self):
        self.assertEqual(ConsoleMessage(severity="SEVERE", text="x").severity, "error")

    def test_unknown_falls_back_to_info(self):
        self.assertEqual(ConsoleMessage(severity="weird", text="x").severity, "info")


class TestErrorBudget(unittest.TestCase):

    def test_negative_max_rejected(self):
        with self.assertRaises(ConsoleBudgetError):
            ErrorBudget(max_errors=-1)
        with self.assertRaises(ConsoleBudgetError):
            ErrorBudget(max_warnings=-1)

    def test_bad_sample_size_rejected(self):
        with self.assertRaises(ConsoleBudgetError):
            ErrorBudget(sample_size=-1)


class TestEvaluate(unittest.TestCase):

    def test_clean_run_passes(self):
        report = evaluate(
            [ConsoleMessage(severity="log", text="ok")],
            ErrorBudget(max_errors=0, max_warnings=0),
        )
        self.assertTrue(report.passed)
        self.assertEqual(report.error_count, 0)

    def test_error_over_budget_fails(self):
        report = evaluate(
            [ConsoleMessage(severity="error", text="boom")],
            ErrorBudget(max_errors=0),
        )
        self.assertFalse(report.passed)
        self.assertIn("errors", report.breaches[0])
        with self.assertRaises(ConsoleBudgetError):
            report.raise_if_failed()

    def test_warning_budget_independent(self):
        msgs = [ConsoleMessage(severity="warning", text=f"w{i}") for i in range(3)]
        report = evaluate(msgs, ErrorBudget(max_errors=0, max_warnings=2))
        self.assertFalse(report.passed)
        self.assertEqual(report.warning_count, 3)

    def test_count_warnings_off(self):
        msgs = [ConsoleMessage(severity="warning", text="w") for _ in range(100)]
        report = evaluate(msgs, ErrorBudget(max_errors=0, max_warnings=0, count_warnings=False))
        self.assertTrue(report.passed)
        self.assertEqual(report.warning_count, 0)

    def test_pattern_allowlist(self):
        msgs = [
            ConsoleMessage(severity="error", text="ResizeObserver loop ignored"),
            ConsoleMessage(severity="error", text="real crash"),
        ]
        report = evaluate(msgs, ErrorBudget(
            max_errors=0, ignore_patterns=[re.compile("ResizeObserver")],
        ))
        self.assertEqual(report.ignored_count, 1)
        self.assertEqual(report.error_count, 1)
        self.assertFalse(report.passed)

    def test_pattern_as_string(self):
        msgs = [ConsoleMessage(severity="error", text="foo bar")]
        report = evaluate(msgs, ErrorBudget(
            max_errors=0, ignore_patterns=["bar"],
        ))
        self.assertEqual(report.ignored_count, 1)
        self.assertTrue(report.passed)

    def test_bad_pattern_rejected(self):
        with self.assertRaises(ConsoleBudgetError):
            evaluate([], ErrorBudget(ignore_patterns=["[invalid"]))

    def test_sampled_capped(self):
        msgs = [ConsoleMessage(severity="error", text=f"e{i}") for i in range(50)]
        report = evaluate(msgs, ErrorBudget(max_errors=999, sample_size=5))
        self.assertEqual(len(report.sampled), 5)

    def test_non_message_rejected(self):
        with self.assertRaises(ConsoleBudgetError):
            evaluate(["not a message"], ErrorBudget())  # type: ignore[list-item]

    def test_bad_budget_rejected(self):
        with self.assertRaises(ConsoleBudgetError):
            evaluate([], "not a budget")  # type: ignore[arg-type]


class TestSeleniumAdapter(unittest.TestCase):

    def test_parses_entries(self):
        entries = [
            {"level": "SEVERE", "message": "TypeError: foo", "timestamp": 1700000000000},
            {"level": "WARNING", "message": "deprecation", "timestamp": 1700000000100},
        ]
        msgs = from_selenium_log(entries)
        self.assertEqual([m.severity for m in msgs], ["error", "warning"])

    def test_skips_non_dicts(self):
        self.assertEqual(from_selenium_log(["string", None]), [])  # type: ignore[list-item]


class TestCdpAdapters(unittest.TestCase):

    def test_console_event_text_joined(self):
        events = [{
            "type": "error",
            "args": [{"value": "boom"}, {"value": "at line"}, {"description": "Error: x"}],
            "timestamp": 1700000000000,
        }]
        msgs = from_cdp_console_events(events)
        self.assertEqual(msgs[0].severity, "error")
        self.assertIn("boom", msgs[0].text)
        self.assertIn("Error: x", msgs[0].text)

    def test_exception_event_normalised(self):
        events = [{
            "timestamp": 1700000000000,
            "exceptionDetails": {
                "exception": {"description": "ReferenceError: x is not defined"},
                "url": "https://app/main.js",
                "lineNumber": 42,
            },
        }]
        msgs = from_cdp_exception_events(events)
        self.assertEqual(msgs[0].severity, "error")
        self.assertIn("ReferenceError", msgs[0].text)
        self.assertEqual(msgs[0].line, 42)


class TestBudgetReportDataclass(unittest.TestCase):

    def test_default_passing_does_not_raise(self):
        BudgetReport(passed=True, error_count=0, warning_count=0, ignored_count=0).raise_if_failed()


if __name__ == "__main__":
    unittest.main()
