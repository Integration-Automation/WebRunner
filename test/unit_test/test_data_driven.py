import json
import os
import tempfile
import unittest
from pathlib import Path

from je_web_runner.utils.data_driven.data_runner import (
    DataDrivenError,
    expand_with_row,
    load_dataset_csv,
    load_dataset_json,
    run_with_dataset,
)


class TestDatasetLoaders(unittest.TestCase):

    def test_load_csv_round_trip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "data.csv")
            Path(path).write_text("name,age\nalice,30\nbob,25\n", encoding="utf-8")
            rows = load_dataset_csv(path)
            self.assertEqual(rows, [{"name": "alice", "age": "30"}, {"name": "bob", "age": "25"}])

    def test_load_json_round_trip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "data.json")
            Path(path).write_text(json.dumps([{"name": "alice"}]), encoding="utf-8")
            rows = load_dataset_json(path)
            self.assertEqual(rows, [{"name": "alice"}])

    def test_missing_csv_raises(self):
        with self.assertRaises(DataDrivenError):
            load_dataset_csv("/no/such/path.csv")

    def test_json_must_be_list(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "data.json")
            Path(path).write_text(json.dumps({"x": 1}), encoding="utf-8")
            with self.assertRaises(DataDrivenError):
                load_dataset_json(path)


class TestRowExpansion(unittest.TestCase):

    def test_expand_string(self):
        result = expand_with_row("hi ${ROW.name}", {"name": "alice"})
        self.assertEqual(result, "hi alice")

    def test_expand_action_dict_and_list(self):
        action = [
            ["WR_to_url", {"url": "https://e.com/${ROW.path}"}],
            ["WR_input_to_element", {"input_value": "${ROW.user}"}],
        ]
        result = expand_with_row(action, {"path": "login", "user": "bob"})
        self.assertEqual(result[0][1]["url"], "https://e.com/login")
        self.assertEqual(result[1][1]["input_value"], "bob")

    def test_unknown_column_raises(self):
        with self.assertRaises(DataDrivenError):
            expand_with_row("${ROW.nope}", {"name": "x"})

    def test_non_string_passes_through(self):
        self.assertEqual(expand_with_row(7, {}), 7)
        self.assertIsNone(expand_with_row(None, {}))


class TestRunWithDataset(unittest.TestCase):

    def test_runner_called_per_row_with_expanded_action(self):
        captured = []

        def runner(action):
            captured.append(action)
            return f"ran_{len(captured)}"

        action = [["WR_to_url", {"url": "https://e/${ROW.path}"}]]
        rows = [{"path": "a"}, {"path": "b"}]
        results = run_with_dataset(action, rows, runner)
        self.assertEqual(results, ["ran_1", "ran_2"])
        self.assertEqual(captured[0][0][1]["url"], "https://e/a")
        self.assertEqual(captured[1][0][1]["url"], "https://e/b")


if __name__ == "__main__":
    unittest.main()
