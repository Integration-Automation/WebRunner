import json
import os
import tempfile
import unittest
from pathlib import Path

from je_web_runner.utils.har_diff.har_diff import (
    HarDiffError,
    diff_har,
    diff_har_files,
)


def _har(entries):
    return {"log": {"entries": entries}}


def _entry(method, url, status):
    return {
        "request": {"method": method, "url": url},
        "response": {"status": status},
    }


class TestDiffHar(unittest.TestCase):

    def test_added_and_removed(self):
        left = _har([_entry("GET", "https://e/a", 200)])
        right = _har([_entry("GET", "https://e/b", 200)])
        diff = diff_har(left, right)
        self.assertEqual(len(diff["added"]), 1)
        self.assertEqual(diff["added"][0]["url"], "https://e/b")
        self.assertEqual(len(diff["removed"]), 1)
        self.assertEqual(diff["removed"][0]["url"], "https://e/a")
        self.assertEqual(diff["changed"], [])

    def test_status_change_reported(self):
        left = _har([_entry("GET", "https://e/api", 200)])
        right = _har([_entry("GET", "https://e/api", 500)])
        diff = diff_har(left, right)
        self.assertEqual(diff["added"], [])
        self.assertEqual(diff["removed"], [])
        self.assertEqual(len(diff["changed"]), 1)
        self.assertEqual(diff["changed"][0]["left_status"], 200)
        self.assertEqual(diff["changed"][0]["right_status"], 500)

    def test_method_difference_treated_as_separate(self):
        left = _har([_entry("GET", "https://e/x", 200)])
        right = _har([_entry("POST", "https://e/x", 201)])
        diff = diff_har(left, right)
        self.assertEqual(len(diff["added"]), 1)
        self.assertEqual(len(diff["removed"]), 1)

    def test_string_input_parses(self):
        left = json.dumps(_har([]))
        right = json.dumps(_har([_entry("GET", "https://e/a", 200)]))
        diff = diff_har(left, right)
        self.assertEqual(len(diff["added"]), 1)

    def test_invalid_har_raises(self):
        with self.assertRaises(HarDiffError):
            diff_har({"no_log": True}, {"no_log": True})

    def test_invalid_json_string_raises(self):
        with self.assertRaises(HarDiffError):
            diff_har("not-json", "not-json")


class TestDiffHarFiles(unittest.TestCase):

    def test_round_trip(self):
        left_har = _har([_entry("GET", "https://e/a", 200)])
        right_har = _har([_entry("GET", "https://e/a", 500)])
        with tempfile.TemporaryDirectory() as tmpdir:
            left_path = os.path.join(tmpdir, "l.har")
            right_path = os.path.join(tmpdir, "r.har")
            Path(left_path).write_text(json.dumps(left_har), encoding="utf-8")
            Path(right_path).write_text(json.dumps(right_har), encoding="utf-8")
            diff = diff_har_files(left_path, right_path)
            self.assertEqual(len(diff["changed"]), 1)

    def test_missing_file_raises(self):
        with self.assertRaises(HarDiffError):
            diff_har_files("/no/such/a.har", "/no/such/b.har")


if __name__ == "__main__":
    unittest.main()
