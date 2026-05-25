"""Unit tests for je_web_runner.utils.test_naming_lint."""
import unittest

from je_web_runner.utils.test_naming_lint.lint import (
    Convention,
    NamingFinding,
    NamingLintError,
    assert_clean,
    lint_many,
    lint_test_name,
)


class TestShouldWhen(unittest.TestCase):

    def test_pass(self):
        out = lint_test_name(
            "test_should_log_in_when_credentials_valid",
            convention=Convention.SHOULD_WHEN,
        )
        self.assertEqual(out, [])

    def test_fail(self):
        out = lint_test_name(
            "test_login_works",
            convention=Convention.SHOULD_WHEN,
        )
        rules = {f.rule for f in out}
        self.assertIn("violates-snake_case_should_when", rules)


class TestGivenWhenThen(unittest.TestCase):

    def test_pass(self):
        out = lint_test_name(
            "test_given_logged_in_user_when_clicks_profile_then_shows_avatar",
            convention=Convention.GIVEN_WHEN_THEN,
        )
        self.assertEqual(out, [])

    def test_fail(self):
        out = lint_test_name(
            "test_login_works",
            convention=Convention.GIVEN_WHEN_THEN,
        )
        self.assertTrue(any(f.rule.startswith("violates") for f in out))


class TestCamelSubject(unittest.TestCase):

    def test_pass(self):
        out = lint_test_name(
            "test_userLoginsSuccessfully",
            convention=Convention.CAMEL_SUBJECT,
        )
        self.assertEqual(out, [])


class TestSmells(unittest.TestCase):

    def test_missing_prefix(self):
        out = lint_test_name("login_works",
                             convention=Convention.SHOULD_WHEN)
        self.assertIn("missing-prefix", {f.rule for f in out})

    def test_double_underscore(self):
        out = lint_test_name(
            "test__should_log_in_when_credentials_valid",
            convention=Convention.SHOULD_WHEN,
        )
        self.assertIn("double-underscore", {f.rule for f in out})

    def test_too_long(self):
        long_name = "test_should_" + "x" * 200 + "_when_y"
        out = lint_test_name(long_name, convention=Convention.SHOULD_WHEN)
        self.assertIn("too-long", {f.rule for f in out})


class TestArgs(unittest.TestCase):

    def test_bad_name(self):
        with self.assertRaises(NamingLintError):
            lint_test_name(123, convention=Convention.SHOULD_WHEN)  # NOSONAR python:S5655 - deliberate bad input

    def test_bad_convention(self):
        with self.assertRaises(NamingLintError):
            lint_test_name("test_x", convention="weird")

    def test_bad_length(self):
        with self.assertRaises(NamingLintError):
            lint_test_name("test_x", convention=Convention.SHOULD_WHEN,
                           max_length=5)


class TestLintMany(unittest.TestCase):

    def test_aggregates(self):
        out = lint_many(
            ["test_x", "bad_name"],
            convention=Convention.SHOULD_WHEN,
        )
        self.assertGreaterEqual(len(out), 2)


class TestAssertClean(unittest.TestCase):

    def test_pass(self):
        assert_clean([])

    def test_fail(self):
        with self.assertRaises(NamingLintError):
            assert_clean([NamingFinding(rule="x", test="t", message="m")])


if __name__ == "__main__":
    unittest.main()
