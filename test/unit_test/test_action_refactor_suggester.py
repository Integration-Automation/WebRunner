"""Unit tests for je_web_runner.utils.action_refactor_suggester."""
import unittest

from je_web_runner.utils.action_refactor_suggester.suggest import (
    ActionRefactorSuggesterError,
    Severity,
    Suggestion,
    analyze,
    assert_no_warns_or_errors,
    report_markdown,
)


def _step(name, **kw):
    return {"action_name": name, **kw}


class TestAnalyze(unittest.TestCase):

    def test_hard_sleep(self):
        out = analyze([_step("sleep", value=2)])
        self.assertIn("no-hard-sleep", [s.rule for s in out])

    def test_numeric_wait_is_sleep(self):
        out = analyze([_step("wait", value=3)])
        self.assertIn("no-hard-sleep", [s.rule for s in out])

    def test_positional_xpath(self):
        out = analyze([_step("click", by="xpath",
                             by_value="//div[3]/span[2]")])
        self.assertIn("no-positional-xpath", [s.rule for s in out])

    def test_dup_locator(self):
        out = analyze([
            _step("click", by_value="#btn"),
            _step("click", by_value="#btn"),
            _step("click", by_value="#btn"),
        ])
        self.assertIn("extract-duplicated-locator", [s.rule for s in out])

    def test_english_assertion(self):
        out = analyze([_step("assert_text",
                             expected="Welcome to the application, friend!")])
        self.assertIn("prefer-translation-key", [s.rule for s in out])

    def test_click_wait_click(self):
        out = analyze([
            _step("click_element", element_name="a"),
            _step("wait_visible", element_name="b"),
            _step("click_element", element_name="c"),
        ])
        self.assertIn("extract-helper", [s.rule for s in out])

    def test_clean(self):
        self.assertEqual(analyze([_step("click_element", element_name="x")]), [])

    def test_bad_seq(self):
        with self.assertRaises(ActionRefactorSuggesterError):
            analyze("nope")

    def test_bad_step(self):
        with self.assertRaises(ActionRefactorSuggesterError):
            analyze(["nope"])

    def test_sort_order_errors_first(self):
        out = analyze([
            _step("sleep", value=1),  # WARN
            _step("assert_text",
                  expected="Welcome to the application, friend!"),  # INFO
        ])
        severities = [s.severity for s in out]
        # WARNs sort before INFOs
        self.assertEqual(severities[0], Severity.WARN)


class TestReport(unittest.TestCase):

    def test_empty(self):
        self.assertIn("clean", report_markdown([]))

    def test_renders(self):
        md = report_markdown([
            Suggestion(rule="x", severity=Severity.WARN,
                       message="msg", step_indexes=[1, 2]),
        ])
        self.assertIn("**x**", md)
        self.assertIn("[1, 2]", md)


class TestAssert(unittest.TestCase):

    def test_pass(self):
        assert_no_warns_or_errors([])

    def test_pass_info_only(self):
        assert_no_warns_or_errors([Suggestion(rule="x",
                                              severity=Severity.INFO,
                                              message="m")])

    def test_fail(self):
        with self.assertRaises(ActionRefactorSuggesterError):
            assert_no_warns_or_errors([Suggestion(rule="x",
                                                  severity=Severity.WARN,
                                                  message="m")])


if __name__ == "__main__":
    unittest.main()
