"""Unit tests for je_web_runner.utils.pr_title_generator."""
import unittest

from je_web_runner.utils.pr_title_generator.generate import (
    PrTitleGeneratorError,
    assert_conventional,
    suggest_title,
    suggest_title_with_llm,
)


class TestSuggest(unittest.TestCase):

    def test_test_directory_classified_as_test(self):
        title = suggest_title(
            files=["test/unit_test/test_foo.py"],
            commits=["Add foo unit test"],
        )
        self.assertTrue(title.startswith("test"))

    def test_docs_md(self):
        title = suggest_title(files=["README.md"], commits=["Update README"])
        self.assertTrue(title.startswith("docs"))

    def test_ci(self):
        title = suggest_title(
            files=[".github/workflows/build.yml"],
            commits=["bump action"],
        )
        self.assertTrue(title.startswith("ci"))

    def test_build(self):
        title = suggest_title(files=["pyproject.toml"],
                              commits=["bump deps"])
        self.assertTrue(title.startswith("build"))

    def test_fix_from_commit_prefix(self):
        title = suggest_title(files=["src/x.py"],
                              commits=["fix: handle null"])
        self.assertTrue(title.startswith("fix"))

    def test_scope_from_src(self):
        title = suggest_title(files=["src/auth/login.py"],
                              commits=["Add login validation"])
        self.assertIn("(auth)", title)

    def test_breaking_marker(self):
        title = suggest_title(files=["src/api/x.py"],
                              commits=["Rename endpoint"],
                              breaking=True)
        self.assertIn("!", title)

    def test_truncates_long(self):
        title = suggest_title(
            files=["src/x.py"],
            commits=["Add a very long summary " + "x" * 200],
        )
        self.assertLessEqual(len(title), 72)

    def test_empty_rejected(self):
        with self.assertRaises(PrTitleGeneratorError):
            suggest_title(files=[], commits=[])

    def test_bad_files_type(self):
        with self.assertRaises(PrTitleGeneratorError):
            suggest_title(files="nope", commits=[])

    def test_bad_commits_type(self):
        with self.assertRaises(PrTitleGeneratorError):
            suggest_title(files=[], commits="nope")

    def test_default_feat(self):
        title = suggest_title(files=["other/x.py"], commits=["new feature"])
        self.assertTrue(title.startswith("feat"))


class TestLlm(unittest.TestCase):

    def test_pass(self):
        title = suggest_title_with_llm(
            files=["x"], commits=["y"],
            titler=lambda f, c: "feat(x): great",
        )
        self.assertEqual(title, "feat(x): great")

    def test_non_callable(self):
        with self.assertRaises(PrTitleGeneratorError):
            suggest_title_with_llm([], [], titler="nope")

    def test_bad_return(self):
        with self.assertRaises(PrTitleGeneratorError):
            suggest_title_with_llm([], [], titler=lambda f, c: "")

    def test_truncates(self):
        title = suggest_title_with_llm(
            ["x"], ["y"], titler=lambda f, c: "feat: " + "x" * 200,
        )
        self.assertLessEqual(len(title), 72)

    def test_propagates(self):
        def boom(_f, _c):
            raise RuntimeError("boom")
        with self.assertRaises(PrTitleGeneratorError):
            suggest_title_with_llm(["x"], ["y"], titler=boom)


class TestAssertConventional(unittest.TestCase):

    def test_pass(self):
        assert_conventional("feat(api): add login")

    def test_breaking_ok(self):
        assert_conventional("fix(api)!: remove field")

    def test_fail(self):
        with self.assertRaises(PrTitleGeneratorError):
            assert_conventional("update stuff")

    def test_bad_type(self):
        with self.assertRaises(PrTitleGeneratorError):
            assert_conventional(123)  # NOSONAR python:S5655 - deliberate bad input


if __name__ == "__main__":
    unittest.main()
