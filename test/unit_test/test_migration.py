import json
import os
import tempfile
import unittest
from pathlib import Path

from je_web_runner.utils.linter.migration import (
    MigrationError,
    migrate_action,
    migrate_action_file,
    migrate_directory,
)


class TestMigrateAction(unittest.TestCase):

    def test_legacy_names_rewritten_in_list_form(self):
        new_data, changes = migrate_action([
            ["WR_SaveTestObject", {"test_object_name": "x", "object_type": "ID"}],
            ["WR_input_to_element", {"input_value": "alice"}],
        ])
        self.assertEqual(new_data[0][0], "WR_save_test_object")
        self.assertEqual(new_data[1][0], "WR_element_input")
        self.assertEqual(len(changes), 2)

    def test_unrelated_commands_left_alone(self):
        new_data, changes = migrate_action([["WR_to_url", {"url": "https://e"}]])
        self.assertEqual(new_data, [["WR_to_url", {"url": "https://e"}]])
        self.assertEqual(changes, [])

    def test_dict_form_rewrites_inner_list(self):
        new_data, changes = migrate_action({
            "webdriver_wrapper": [["WR_explict_wait", {"wait_time": 5}]],
            "meta": {"tags": ["smoke"]},
        })
        self.assertEqual(new_data["webdriver_wrapper"][0][0], "WR_explicit_wait")
        self.assertEqual(new_data["meta"], {"tags": ["smoke"]})
        self.assertEqual(len(changes), 1)


class TestMigrateActionFile(unittest.TestCase):

    def test_dry_run_does_not_write(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "a.json")
            payload = [["WR_SaveTestObject", {"test_object_name": "x", "object_type": "ID"}]]
            Path(path).write_text(json.dumps(payload), encoding="utf-8")
            result = migrate_action_file(path, dry_run=True)
            self.assertFalse(result["written"])
            self.assertEqual(len(result["changes"]), 1)
            with open(path, encoding="utf-8") as on_disk:
                self.assertEqual(json.load(on_disk), payload)

    def test_apply_rewrites_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "a.json")
            Path(path).write_text(
                json.dumps([["WR_SaveTestObject", {"test_object_name": "x", "object_type": "ID"}]]),
                encoding="utf-8",
            )
            result = migrate_action_file(path, dry_run=False)
            self.assertTrue(result["written"])
            with open(path, encoding="utf-8") as on_disk:
                self.assertEqual(json.load(on_disk)[0][0], "WR_save_test_object")

    def test_missing_file_raises(self):
        with self.assertRaises(MigrationError):
            migrate_action_file("/no/such/a.json", dry_run=True)


class TestMigrateDirectory(unittest.TestCase):

    def test_walks_subdirectories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            nested = os.path.join(tmpdir, "sub")
            os.makedirs(nested, exist_ok=True)
            Path(os.path.join(tmpdir, "a.json")).write_text(
                json.dumps([["WR_SaveTestObject", {"test_object_name": "x", "object_type": "ID"}]]),
                encoding="utf-8",
            )
            Path(os.path.join(nested, "b.json")).write_text(
                json.dumps([["WR_explict_wait", {"wait_time": 1}]]),
                encoding="utf-8",
            )
            results = migrate_directory(tmpdir, dry_run=True)
            self.assertEqual(len(results), 2)
            self.assertEqual(sum(len(r["changes"]) for r in results), 2)


if __name__ == "__main__":
    unittest.main()
