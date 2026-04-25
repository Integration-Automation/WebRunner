import json
import os
import tempfile
import unittest
from pathlib import Path

from je_web_runner.utils.test_filter.tag_filter import (
    TagFilterError,
    filter_paths,
    match_tags,
    read_metadata,
)


def _write(dir_path, name, payload):
    path = os.path.join(dir_path, name)
    Path(path).write_text(json.dumps(payload), encoding="utf-8")
    return path


class TestReadMetadata(unittest.TestCase):

    def test_no_meta_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _write(tmpdir, "a.json", [["WR_quit"]])
            self.assertEqual(read_metadata(path), {})

    def test_dict_with_meta_returns_meta(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _write(tmpdir, "a.json", {
                "webdriver_wrapper": [["WR_quit"]],
                "meta": {"tags": ["smoke"]},
            })
            self.assertEqual(read_metadata(path), {"tags": ["smoke"]})

    def test_missing_file_raises(self):
        with self.assertRaises(TagFilterError):
            read_metadata("/no/such/file.json")


class TestMatchTags(unittest.TestCase):

    def test_no_filters_keeps_everything(self):
        self.assertTrue(match_tags({"tags": []}))
        self.assertTrue(match_tags({}))

    def test_include_requires_match(self):
        self.assertTrue(match_tags({"tags": ["smoke"]}, include=["smoke"]))
        self.assertFalse(match_tags({"tags": ["regression"]}, include=["smoke"]))
        self.assertFalse(match_tags({}, include=["smoke"]))

    def test_exclude_blocks_match(self):
        self.assertFalse(match_tags({"tags": ["slow"]}, exclude=["slow"]))
        self.assertTrue(match_tags({"tags": ["fast"]}, exclude=["slow"]))


class TestFilterPaths(unittest.TestCase):

    def test_filter_by_include(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            smoke = _write(tmpdir, "a.json", {"webdriver_wrapper": [], "meta": {"tags": ["smoke"]}})
            regression = _write(tmpdir, "b.json", {"webdriver_wrapper": [], "meta": {"tags": ["regression"]}})
            self.assertEqual(filter_paths([smoke, regression], include=["smoke"]), [smoke])

    def test_filter_by_exclude(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            slow = _write(tmpdir, "a.json", {"webdriver_wrapper": [], "meta": {"tags": ["slow"]}})
            fast = _write(tmpdir, "b.json", {"webdriver_wrapper": [], "meta": {"tags": ["fast"]}})
            self.assertEqual(filter_paths([slow, fast], exclude=["slow"]), [fast])

    def test_no_filter_keeps_all(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            a = _write(tmpdir, "a.json", [])
            b = _write(tmpdir, "b.json", [])
            self.assertEqual(set(filter_paths([a, b])), {a, b})


if __name__ == "__main__":
    unittest.main()
