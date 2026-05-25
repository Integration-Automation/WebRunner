"""Unit tests for je_web_runner.utils.pre_merge_gate_dsl."""
import unittest

from je_web_runner.utils.pre_merge_gate_dsl.gate import (
    PreMergeGateDslError,
    PrFacts,
    Rule,
    assert_gate_passes,
    evaluate,
    parse_rules,
)


class TestPrFacts(unittest.TestCase):

    def test_docs_only_true(self):
        self.assertTrue(PrFacts(files_changed=["README.md"]).is_docs_only)

    def test_docs_only_false(self):
        self.assertFalse(
            PrFacts(files_changed=["src/x.py", "README.md"]).is_docs_only,
        )

    def test_has_path(self):
        self.assertTrue(
            PrFacts(files_changed=["src/payments/x.py"])
            .has_path("src/payments/*"),
        )


class TestRule(unittest.TestCase):

    def test_basic(self):
        Rule(when="facts.is_docs_only", require=["one_reviewer"])

    def test_empty_when(self):
        with self.assertRaises(PreMergeGateDslError):
            Rule(when="", require=["x"])

    def test_empty_require(self):
        with self.assertRaises(PreMergeGateDslError):
            Rule(when="facts.is_docs_only", require=[])


class TestParseRules(unittest.TestCase):

    def test_basic(self):
        rules = parse_rules([
            {"when": "facts.is_docs_only", "require": ["one_reviewer"]},
        ])
        self.assertEqual(len(rules), 1)

    def test_non_list(self):
        with self.assertRaises(PreMergeGateDslError):
            parse_rules("nope")

    def test_non_dict(self):
        with self.assertRaises(PreMergeGateDslError):
            parse_rules(["nope"])


class TestEvaluate(unittest.TestCase):

    def test_docs_only_pass(self):
        result = evaluate(
            [Rule(when="facts.is_docs_only", require=["one_reviewer"])],
            PrFacts(files_changed=["README.md"], review_approvals=1),
        )
        self.assertTrue(result.passed)

    def test_docs_only_fail(self):
        result = evaluate(
            [Rule(when="facts.is_docs_only", require=["one_reviewer"])],
            PrFacts(files_changed=["README.md"], review_approvals=0),
        )
        self.assertFalse(result.passed)

    def test_payments_path_strict(self):
        result = evaluate(
            [Rule(when="facts.has_path('src/payments/*')",
                  require=["two_reviewers", "pr_title_has_jira"])],
            PrFacts(files_changed=["src/payments/x.py"],
                    review_approvals=1, title="big update"),
        )
        self.assertFalse(result.passed)
        self.assertEqual(len(result.failures), 2)

    def test_skip_rule_when_unmet(self):
        result = evaluate(
            [Rule(when="facts.is_docs_only", require=["two_reviewers"])],
            PrFacts(files_changed=["src/x.py"], review_approvals=0),
        )
        self.assertTrue(result.passed)

    def test_unknown_predicate(self):
        with self.assertRaises(PreMergeGateDslError):
            evaluate(
                [Rule(when="facts.is_docs_only", require=["nonsense"])],
                PrFacts(files_changed=["README.md"]),
            )

    def test_unsafe_expression_blocked(self):
        with self.assertRaises(PreMergeGateDslError):
            evaluate(
                [Rule(when="__import__('os').system('rm -rf /')",
                      require=["one_reviewer"])],
                PrFacts(),
            )

    def test_non_bool_when_blocked(self):
        with self.assertRaises(PreMergeGateDslError):
            evaluate(
                [Rule(when="facts.title", require=["one_reviewer"])],
                PrFacts(title="x"),
            )

    def test_bad_facts_type(self):
        with self.assertRaises(PreMergeGateDslError):
            evaluate([], "nope")

    def test_custom_predicate(self):
        result = evaluate(
            [Rule(when="facts.is_docs_only", require=["custom"])],
            PrFacts(files_changed=["README.md"]),
            predicates={"custom": lambda f: None},
        )
        self.assertTrue(result.passed)


class TestBuiltins(unittest.TestCase):

    def test_jira_pass(self):
        result = evaluate(
            [Rule(when="facts.is_docs_only", require=["pr_title_has_jira"])],
            PrFacts(title="ABC-123 update", files_changed=["README.md"]),
        )
        self.assertTrue(result.passed)

    def test_flake_regression(self):
        result = evaluate(
            [Rule(when="facts.is_docs_only",
                  require=["no_flake_regression"])],
            PrFacts(files_changed=["README.md"], flake_score_delta=0.5),
        )
        self.assertFalse(result.passed)

    def test_small_pr(self):
        result = evaluate(
            [Rule(when="facts.is_docs_only", require=["small_pr"])],
            PrFacts(files_changed=["README.md"], additions=500, deletions=10),
        )
        self.assertFalse(result.passed)

    def test_no_failing_checks(self):
        result = evaluate(
            [Rule(when="facts.is_docs_only",
                  require=["no_failing_checks"])],
            PrFacts(files_changed=["README.md"], failing_checks=["unit"]),
        )
        self.assertFalse(result.passed)


class TestAssert(unittest.TestCase):

    def test_pass(self):
        from je_web_runner.utils.pre_merge_gate_dsl.gate import GateResult
        assert_gate_passes(GateResult(passed=True))

    def test_fail(self):
        from je_web_runner.utils.pre_merge_gate_dsl.gate import GateResult
        with self.assertRaises(PreMergeGateDslError):
            assert_gate_passes(GateResult(passed=False, failures=["x"]))


if __name__ == "__main__":
    unittest.main()
