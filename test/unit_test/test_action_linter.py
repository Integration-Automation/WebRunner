import unittest

from je_web_runner.utils.linter.action_linter import (
    lint_action,
    severity_counts,
)


class TestLegacyNames(unittest.TestCase):

    def test_legacy_names_flagged(self):
        findings = lint_action([
            ["WR_SaveTestObject", {"test_object_name": "x", "object_type": "ID"}],
            ["WR_explict_wait", {"wait_time": 5}],
            ["WR_save_test_object", {"test_object_name": "y", "object_type": "ID"}],
        ])
        rules = [f["rule"] for f in findings]
        self.assertIn("legacy_name", rules)
        legacy = [f for f in findings if f["rule"] == "legacy_name"]
        self.assertEqual(len(legacy), 2)


class TestArbitraryScript(unittest.TestCase):

    def test_execute_script_warned(self):
        findings = lint_action([["WR_execute_script", {"script": "1+1"}]])
        self.assertTrue(any(f["rule"] == "arbitrary_script" for f in findings))

    def test_pw_evaluate_warned(self):
        findings = lint_action([["WR_pw_evaluate", {"expression": "1"}]])
        self.assertTrue(any(f["rule"] == "arbitrary_script" for f in findings))


class TestHardcodedUrl(unittest.TestCase):

    def test_literal_url_in_args_flagged(self):
        findings = lint_action([["WR_to_url", {"url": "https://hard.example.com/login"}]])
        self.assertTrue(any(f["rule"] == "hardcoded_url" for f in findings))

    def test_env_placeholder_not_flagged(self):
        findings = lint_action([["WR_to_url", {"url": "${ENV.BASE_URL}/login"}]])
        self.assertFalse(any(f["rule"] == "hardcoded_url" for f in findings))


class TestEmptyKwargs(unittest.TestCase):

    def test_empty_kwargs_info(self):
        findings = lint_action([["WR_to_url", {}]])
        self.assertTrue(any(f["rule"] == "empty_kwargs" for f in findings))


class TestDuplicateConsecutive(unittest.TestCase):

    def test_two_identical_actions_flagged(self):
        findings = lint_action([
            ["WR_to_url", {"url": "https://example.com"}],
            ["WR_to_url", {"url": "https://example.com"}],
        ])
        self.assertTrue(any(f["rule"] == "duplicate_consecutive" for f in findings))


class TestMissingTags(unittest.TestCase):

    def test_dict_form_without_meta_tags_info(self):
        findings = lint_action({"webdriver_wrapper": [["WR_quit_all"]]})
        self.assertTrue(any(f["rule"] == "missing_tags" for f in findings))

    def test_dict_form_with_tags_no_finding(self):
        findings = lint_action({
            "webdriver_wrapper": [["WR_quit_all"]],
            "meta": {"tags": ["smoke"]},
        })
        self.assertFalse(any(f["rule"] == "missing_tags" for f in findings))


class TestSeverityCounts(unittest.TestCase):

    def test_counts(self):
        findings = [
            {"rule": "a", "severity": "warning"},
            {"rule": "b", "severity": "warning"},
            {"rule": "c", "severity": "info"},
        ]
        self.assertEqual(severity_counts(findings), {"warning": 2, "info": 1})


if __name__ == "__main__":
    unittest.main()
