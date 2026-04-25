import json
import os
import tempfile
import unittest

from je_web_runner.utils.exception.exceptions import WebRunnerExecuteException
from je_web_runner.utils.json.json_validator import (
    validate_action_file,
    validate_action_files,
    validate_action_json,
)


class TestActionJsonValidator(unittest.TestCase):

    def test_valid_list_of_actions(self):
        data = [
            ["WR_to_url", {"url": "https://example.com"}],
            ["WR_quit"],
        ]
        self.assertTrue(validate_action_json(data))

    def test_valid_dict_with_webdriver_wrapper_key(self):
        data = {"webdriver_wrapper": [["WR_quit"]]}
        self.assertTrue(validate_action_json(data))

    def test_positional_args_accepted(self):
        data = [["WR_to_url", ["https://example.com"]]]
        self.assertTrue(validate_action_json(data))

    def test_top_level_must_be_list_or_dict(self):
        with self.assertRaises(WebRunnerExecuteException):
            validate_action_json("not a list")

    def test_dict_missing_required_key(self):
        with self.assertRaises(WebRunnerExecuteException):
            validate_action_json({"wrong_key": []})

    def test_empty_action_list_rejected(self):
        with self.assertRaises(WebRunnerExecuteException):
            validate_action_json([])

    def test_action_must_be_list(self):
        with self.assertRaises(WebRunnerExecuteException):
            validate_action_json([{"WR_quit": {}}])

    def test_action_with_too_many_elements(self):
        with self.assertRaises(WebRunnerExecuteException):
            validate_action_json([["WR_to_url", {"url": "a"}, "extra"]])

    def test_command_name_must_be_non_empty_string(self):
        with self.assertRaises(WebRunnerExecuteException):
            validate_action_json([[""]])
        with self.assertRaises(WebRunnerExecuteException):
            validate_action_json([[123]])

    def test_args_must_be_dict_or_sequence(self):
        with self.assertRaises(WebRunnerExecuteException):
            validate_action_json([["WR_to_url", "string-args"]])

    def test_validate_action_file_round_trip(self):
        with tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8"
        ) as temp_file:
            json.dump([["WR_quit"]], temp_file)
            path = temp_file.name
        try:
            self.assertTrue(validate_action_file(path))
            self.assertTrue(validate_action_files([path]))
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
