"""Unit tests for je_web_runner.utils.test_categorizer."""
import json
import tempfile
import unittest
from pathlib import Path

from je_web_runner.utils.test_categorizer.categorizer import (
    CategoryAssignment,
    Rule,
    TagDistribution,
    TestCategorizerError,
    aggregate,
    categorize_actions,
    categorize_dir,
    categorize_file,
)


def _smoke():
    return [
        {"WR_to_url": ["https://x"]},
        {"WR_click_element": ["id", "go"]},
        {"WR_assert_element_text": ["id", "status", "OK"]},
    ]


def _perf():
    return [
        {"WR_to_url": ["https://x"]},
        {"WR_perf_capture_metrics": []},
        {"WR_lighthouse_run": []},
    ]


def _a11y():
    return [
        {"WR_to_url": ["https://x"]},
        {"WR_axe_audit": []},
    ]


def _security():
    return [
        {"WR_to_url": ["https://x"]},
        {"WR_csrf_check": []},
    ]


def _data_driven():
    return [{"WR_to_url": ["https://x"]}] + [
        {"WR_input_to_element": ["id", f"f{i}", "v"]} for i in range(50)
    ]


def _visual():
    return [
        {"WR_to_url": ["https://x"]},
        {"WR_snapshot_take": ["#a"]},
    ]


def _api():
    return [{"WR_http_request": ["GET", "/api/x"]}]


class TestCategorize(unittest.TestCase):

    def test_smoke(self):
        self.assertIn("smoke", categorize_actions(_smoke()))

    def test_regression_over_threshold(self):
        long_actions = _smoke() + [{"WR_click_element": ["id", "x"]}] * 10
        tags = categorize_actions(long_actions)
        self.assertIn("regression", tags)
        self.assertNotIn("smoke", tags)

    def test_perf(self):
        self.assertIn("perf", categorize_actions(_perf()))

    def test_a11y(self):
        self.assertIn("a11y", categorize_actions(_a11y()))

    def test_security(self):
        self.assertIn("security", categorize_actions(_security()))

    def test_data_driven(self):
        self.assertIn("data_driven", categorize_actions(_data_driven()))

    def test_visual(self):
        self.assertIn("visual", categorize_actions(_visual()))

    def test_api(self):
        self.assertIn("api", categorize_actions(_api()))

    def test_multiple_tags(self):
        actions = _smoke() + [{"WR_axe_audit": []}]
        tags = categorize_actions(actions)
        self.assertIn("smoke", tags)
        self.assertIn("a11y", tags)

    def test_no_tags_empty(self):
        self.assertEqual(categorize_actions([]), [])

    def test_rejects_non_list(self):
        with self.assertRaises(TestCategorizerError):
            categorize_actions("not list")  # type: ignore[arg-type]

    def test_rejects_non_rule(self):
        with self.assertRaises(TestCategorizerError):
            categorize_actions([], rules=["not a rule"])  # type: ignore[list-item]

    def test_matcher_exception(self):
        def _bad_matcher(_actions):
            raise RuntimeError("oops")
        bad_rule = Rule(tag="bad", matcher=_bad_matcher)
        with self.assertRaises(TestCategorizerError):
            categorize_actions([], rules=[bad_rule])


class TestFileAndDir(unittest.TestCase):

    def test_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.json"
            path.write_text(json.dumps(_smoke()), encoding="utf-8")
            result = categorize_file(path)
            self.assertIn("smoke", result.tags)
            self.assertEqual(result.action_count, 3)

    def test_file_missing(self):
        with self.assertRaises(TestCategorizerError):
            categorize_file("/no/such/file.json")

    def test_file_bad_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.json"
            path.write_text("not json", encoding="utf-8")
            with self.assertRaises(TestCategorizerError):
                categorize_file(path)

    def test_file_non_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.json"
            path.write_text(json.dumps({"x": 1}), encoding="utf-8")
            with self.assertRaises(TestCategorizerError):
                categorize_file(path)

    def test_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.json").write_text(json.dumps(_smoke()), encoding="utf-8")
            (Path(tmp) / "b.json").write_text(json.dumps(_perf()), encoding="utf-8")
            results = categorize_dir(tmp)
            self.assertEqual(len(results), 2)

    def test_dir_missing(self):
        with self.assertRaises(TestCategorizerError):
            categorize_dir("/no/such/dir")


class TestAggregate(unittest.TestCase):

    def test_counts(self):
        assignments = [
            CategoryAssignment(test_id="a", tags=["smoke", "a11y"]),
            CategoryAssignment(test_id="b", tags=["perf"]),
            CategoryAssignment(test_id="c", tags=[]),
        ]
        dist = aggregate(assignments)
        self.assertEqual(dist.total_tests, 3)
        self.assertEqual(dist.untagged_tests, 1)
        self.assertEqual(dist.by_tag["smoke"], 1)
        self.assertEqual(dist.by_tag["a11y"], 1)

    def test_rejects_non_assignment(self):
        with self.assertRaises(TestCategorizerError):
            aggregate(["nope"])  # type: ignore[list-item]


if __name__ == "__main__":
    unittest.main()
