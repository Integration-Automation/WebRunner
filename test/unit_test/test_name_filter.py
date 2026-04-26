import unittest

from je_web_runner.utils.test_filter.name_filter import (
    NameFilterError,
    build_filter,
    filter_paths,
)


class TestBuildFilter(unittest.TestCase):

    def test_invalid_regex(self):
        with self.assertRaises(NameFilterError):
            build_filter(include=["[unclosed"])

    def test_empty_pattern(self):
        with self.assertRaises(NameFilterError):
            build_filter(include=[""])

    def test_no_rules_passes_everything(self):
        nf = build_filter()
        self.assertTrue(nf.matches("anything.json"))


class TestMatches(unittest.TestCase):

    def test_include_only(self):
        nf = build_filter(include=[r"smoke.*\.json$"])
        self.assertTrue(nf.matches("smoke_login.json"))
        self.assertFalse(nf.matches("regression_login.json"))

    def test_exclude_takes_priority(self):
        nf = build_filter(
            include=[r".*"],
            exclude=[r"slow"],
        )
        self.assertTrue(nf.matches("fast.json"))
        self.assertFalse(nf.matches("slow.json"))

    def test_path_separator_normalised(self):
        nf = build_filter(include=[r"actions/login"])
        self.assertTrue(nf.matches("actions\\login.json"))

    def test_multiple_include_or(self):
        nf = build_filter(include=[r"smoke", r"login"])
        self.assertTrue(nf.matches("login_x.json"))
        self.assertTrue(nf.matches("smoke_y.json"))
        self.assertFalse(nf.matches("regression.json"))


class TestFilterPaths(unittest.TestCase):

    def test_returns_string_list(self):
        result = filter_paths(
            ["actions/smoke_login.json", "actions/regression.json"],
            include=[r"smoke"],
        )
        self.assertEqual(result, ["actions/smoke_login.json"])


if __name__ == "__main__":
    unittest.main()
