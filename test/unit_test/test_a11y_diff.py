import unittest

from je_web_runner.utils.accessibility.a11y_diff import (
    A11yDiffError,
    assert_no_regressions,
    diff_violations,
)


def _violation(rule, *targets, impact="moderate", summary="text"):
    return {
        "id": rule,
        "impact": impact,
        "description": summary,
        "nodes": [{"target": [t]} for t in targets],
    }


class TestDiffViolations(unittest.TestCase):

    def test_added_resolved_persisting(self):
        baseline = [
            _violation("color-contrast", "html>body>h1"),
            _violation("label", "input.email"),
        ]
        current = [
            _violation("color-contrast", "html>body>h1"),
            _violation("button-name", "button.submit"),
        ]
        diff = diff_violations(baseline, current)
        self.assertEqual([a["rule_id"] for a in diff.added], ["button-name"])
        self.assertEqual([r["rule_id"] for r in diff.resolved], ["label"])
        self.assertEqual([p["rule_id"] for p in diff.persisting], ["color-contrast"])
        self.assertTrue(diff.regressed)

    def test_same_rule_different_target(self):
        baseline = [_violation("label", "input.email")]
        current = [_violation("label", "input.password")]
        diff = diff_violations(baseline, current)
        self.assertEqual(len(diff.added), 1)
        self.assertEqual(len(diff.resolved), 1)

    def test_invalid_input_raises(self):
        with self.assertRaises(A11yDiffError):
            diff_violations(["not a dict"], [])

    def test_string_target_supported(self):
        baseline = []
        current = [{"id": "image-alt", "nodes": [{"target": "img.logo"}]}]
        diff = diff_violations(baseline, current)
        self.assertEqual(diff.added[0]["target"], "img.logo")


class TestAssertNoRegressions(unittest.TestCase):

    def test_passes_when_no_added(self):
        baseline = [_violation("label", "input.email")]
        diff = diff_violations(baseline, baseline)
        assert_no_regressions(diff)

    def test_raises_on_added(self):
        baseline = []
        current = [_violation("label", "input.email")]
        diff = diff_violations(baseline, current)
        with self.assertRaises(A11yDiffError):
            assert_no_regressions(diff)

    def test_allow_rules_skips(self):
        baseline = []
        current = [_violation("label", "input.email")]
        diff = diff_violations(baseline, current)
        assert_no_regressions(diff, allow_rules=["label"])


if __name__ == "__main__":
    unittest.main()
