"""Unit tests for je_web_runner.utils.edge_case_generator."""
import json
import tempfile
import unittest
from pathlib import Path

from je_web_runner.utils.ai_assist.llm_assist import set_llm_callable
from je_web_runner.utils.edge_case_generator.generator import (
    EdgeCase,
    EdgeCaseCategory,
    EdgeCaseGeneratorError,
    EdgeCaseSuite,
    generate_edge_cases,
    generate_edge_cases_from_file,
    render_suite_markdown,
    write_suite_to_dir,
)


_GOOD_PAYLOAD = {
    "cases": [
        {
            "name": "extremely long username",
            "category": "boundary",
            "rationale": "5000-char username should reject gracefully",
            "actions": [
                ["WR_element_input",
                 {"test_object_name": "user", "text": "a" * 5000}],
                ["WR_element_assert_text",
                 {"test_object_name": "error", "expected": "Username too long"}],
            ],
            "expected_outcome": "fail",
            "severity": "medium",
        },
        {
            "name": "emoji password",
            "category": "unicode",
            "rationale": "passwords with emoji combining marks",
            "actions": [
                ["WR_element_input",
                 {"test_object_name": "password", "text": "🔒hello👨‍👩‍👦"}],
            ],
            "expected_outcome": "pass",
            "severity": "low",
        },
        {
            "name": "concurrent submit",
            "category": "race",
            "rationale": "double-click submit shouldn't post twice",
            "actions": [
                ["WR_element_click", {"test_object_name": "submit"}],
                ["WR_element_click", {"test_object_name": "submit"}],
            ],
            "expected_outcome": "fail",
            "severity": "high",
        },
    ]
}


SAMPLE_ACTIONS = [
    ["WR_to_url", {"url": "https://shop/login"}],
    ["WR_element_input", {"test_object_name": "user", "text": "alice"}],
    ["WR_element_click", {"test_object_name": "submit"}],
]


class TestGenerateEdgeCases(unittest.TestCase):

    def tearDown(self):
        set_llm_callable(None)

    def test_parses_payload_into_suite(self):
        set_llm_callable(lambda _p: json.dumps(_GOOD_PAYLOAD))
        suite = generate_edge_cases(SAMPLE_ACTIONS, test_name="login", n=3)
        self.assertEqual(len(suite.cases), 3)
        self.assertEqual(suite.cases[0].category, EdgeCaseCategory.BOUNDARY)
        self.assertEqual(suite.cases[2].severity, "high")

    def test_skips_malformed_cases(self):
        payload = {
            "cases": [
                {"name": "ok", "category": "boundary", "rationale": "x",
                 "actions": [["WR_x"]], "expected_outcome": "fail",
                 "severity": "low"},
                {"name": "missing actions"},
                "not even a dict",
            ]
        }
        set_llm_callable(lambda _p: json.dumps(payload))
        suite = generate_edge_cases(SAMPLE_ACTIONS, n=3)
        self.assertEqual(len(suite.cases), 1)

    def test_no_callable_raises(self):
        set_llm_callable(None)
        with self.assertRaises(EdgeCaseGeneratorError):
            generate_edge_cases(SAMPLE_ACTIONS)

    def test_non_list_actions_raise(self):
        with self.assertRaises(EdgeCaseGeneratorError):
            generate_edge_cases("not a list")  # type: ignore[arg-type]

    def test_zero_n_raises(self):
        set_llm_callable(lambda _p: json.dumps(_GOOD_PAYLOAD))
        with self.assertRaises(EdgeCaseGeneratorError):
            generate_edge_cases(SAMPLE_ACTIONS, n=0)

    def test_invalid_json_raises(self):
        set_llm_callable(lambda _p: "not json at all")
        with self.assertRaises(EdgeCaseGeneratorError):
            generate_edge_cases(SAMPLE_ACTIONS)

    def test_unknown_category_falls_to_boundary(self):
        payload = {
            "cases": [{
                "name": "x", "category": "alien", "rationale": "r",
                "actions": [["WR_x"]], "expected_outcome": "fail",
                "severity": "low",
            }]
        }
        set_llm_callable(lambda _p: json.dumps(payload))
        suite = generate_edge_cases(SAMPLE_ACTIONS)
        self.assertEqual(suite.cases[0].category, EdgeCaseCategory.BOUNDARY)

    def test_missing_cases_key_raises(self):
        set_llm_callable(lambda _p: json.dumps({"other": []}))
        with self.assertRaises(EdgeCaseGeneratorError):
            generate_edge_cases(SAMPLE_ACTIONS)


class TestGenerateFromFile(unittest.TestCase):

    def tearDown(self):
        set_llm_callable(None)

    def test_loads_and_generates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "src.json"
            path.write_text(json.dumps(SAMPLE_ACTIONS), encoding="utf-8")
            set_llm_callable(lambda _p: json.dumps(_GOOD_PAYLOAD))
            suite = generate_edge_cases_from_file(path, n=3)
            self.assertEqual(suite.source_test_name, "src")
            self.assertEqual(len(suite.cases), 3)

    def test_missing_file_raises(self):
        with self.assertRaises(EdgeCaseGeneratorError):
            generate_edge_cases_from_file("/no/such.json")

    def test_top_level_not_list_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "src.json"
            path.write_text("{}", encoding="utf-8")
            with self.assertRaises(EdgeCaseGeneratorError):
                generate_edge_cases_from_file(path)


class TestWriteSuiteToDir(unittest.TestCase):

    def test_writes_one_file_per_case(self):
        suite = EdgeCaseSuite(
            source_test_name="login_test",
            cases=[
                EdgeCase(
                    name="long username", category=EdgeCaseCategory.BOUNDARY,
                    rationale="r", actions=[["WR_x"]],
                ),
                EdgeCase(
                    name="emoji password", category=EdgeCaseCategory.UNICODE,
                    rationale="r", actions=[["WR_y"]],
                ),
            ],
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = write_suite_to_dir(suite, tmpdir)
            self.assertEqual(len(paths), 2)
            self.assertTrue(all(p.exists() for p in paths))
            self.assertTrue(paths[0].name.startswith("login_test"))
            self.assertIn("01", paths[0].name)
            payload = json.loads(paths[0].read_text(encoding="utf-8"))
            self.assertEqual(payload, [["WR_x"]])

    def test_handles_blank_names(self):
        suite = EdgeCaseSuite(source_test_name="t", cases=[
            EdgeCase(name="", category=EdgeCaseCategory.RACE,
                     rationale="", actions=[]),
        ])
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = write_suite_to_dir(suite, tmpdir)
            self.assertEqual(len(paths), 1)


class TestRendering(unittest.TestCase):

    def test_table_contains_each_case(self):
        suite = EdgeCaseSuite(
            source_test_name="x",
            cases=[
                EdgeCase(name="a", category=EdgeCaseCategory.BOUNDARY,
                         rationale="r", actions=[]),
                EdgeCase(name="b", category=EdgeCaseCategory.NETWORK,
                         rationale="r", actions=[], severity="high"),
            ],
        )
        md = render_suite_markdown(suite)
        self.assertIn("AI Edge Cases", md)
        self.assertIn("`boundary`", md)
        self.assertIn("`network`", md)
        self.assertIn("`high`", md)

    def test_empty_suite_shows_placeholder(self):
        md = render_suite_markdown(EdgeCaseSuite(source_test_name="x"))
        self.assertIn("no cases parsed", md)


if __name__ == "__main__":
    unittest.main()
