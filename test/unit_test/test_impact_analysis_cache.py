"""``build_index(..., cache_path=...)``: reuse unchanged files, notice every kind of change."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from je_web_runner.utils.impact_analysis import indexer
from je_web_runner.utils.impact_analysis.indexer import build_index


def _write(path: Path, actions) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(actions), encoding="utf-8")


class TestImpactCache(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.suite = Path(tmp.name) / "suite"
        self.cache = Path(tmp.name) / "cache" / "impact.json"
        _write(self.suite / "login.json", [["WR_save_test_object", {"test_object_name": "user"}]])
        _write(self.suite / "shop" / "cart.json", [["WR_to_url", {"url": "https://x.test/cart"}]])

    def _build(self):
        with patch.object(indexer, "_names_in", wraps=indexer._names_in) as parse:
            index = build_index(self.suite, cache_path=self.cache)
        return index, parse.call_count

    def test_unchanged_files_are_not_parsed_again(self):
        first, parsed = self._build()
        self.assertEqual(parsed, 2)
        self.assertTrue(self.cache.is_file())
        second, parsed = self._build()
        self.assertEqual(parsed, 0)
        self.assertEqual(second.by_locator, first.by_locator)
        self.assertEqual(second.files_for_url("cart"), [str(self.suite / "shop" / "cart.json")])

    def test_a_changed_file_is_parsed_and_indexed_again(self):
        self._build()
        _write(self.suite / "login.json", [["WR_save_test_object", {"test_object_name": "password"}]])
        index, parsed = self._build()
        self.assertEqual(parsed, 1)
        self.assertEqual(index.files_for_locator("password"), [str(self.suite / "login.json")])
        self.assertEqual(index.files_for_locator("user"), [])

    def test_a_new_time_with_the_same_content_is_matched_by_hash(self):
        self._build()
        path = self.suite / "login.json"
        later = path.stat().st_mtime_ns + 5_000_000_000
        os.utime(path, ns=(later, later))  # a fresh checkout rewrites every time
        index, parsed = self._build()
        self.assertEqual(parsed, 0)
        self.assertEqual(index.files_for_locator("user"), [str(path)])
        saved = json.loads(self.cache.read_text(encoding="utf-8"))["files"]["login.json"]
        self.assertEqual(saved["mtime_ns"], later)

    def test_new_and_deleted_files(self):
        self._build()
        (self.suite / "shop" / "cart.json").unlink()
        _write(self.suite / "search.json", [["WR_to_url", {"url": "https://x.test/search"}]])
        index, parsed = self._build()
        self.assertEqual(parsed, 1)
        self.assertEqual(index.files_for_url("cart"), [])
        self.assertEqual(set(json.loads(self.cache.read_text(encoding="utf-8"))["files"]),
                         {"login.json", "search.json"})

    def test_an_unparsable_file_is_remembered_as_skipped(self):
        (self.suite / "broken.json").write_text("{not json", encoding="utf-8")
        _index, parsed = self._build()
        self.assertEqual(parsed, 3)
        _index, parsed = self._build()
        self.assertEqual(parsed, 0)

    def test_the_cache_is_rewritten_only_when_something_changed(self):
        self._build()
        with patch.object(indexer, "_save_cache") as save:
            build_index(self.suite, cache_path=self.cache)
        save.assert_not_called()

    def test_a_cache_for_another_tree_or_a_corrupt_cache_is_ignored(self):
        self._build()
        payload = json.loads(self.cache.read_text(encoding="utf-8"))
        for change in ({"glob": "*.json"}, {"version": 0}, {"directory": "elsewhere"}):
            with self.subTest(change=change):
                self.cache.write_text(json.dumps({**payload, **change}), encoding="utf-8")
                _index, parsed = self._build()
                self.assertEqual(parsed, 2)
        self.cache.write_text("{broken", encoding="utf-8")
        _index, parsed = self._build()
        self.assertEqual(parsed, 2)

    def test_without_a_cache_path_nothing_is_written(self):
        build_index(self.suite)
        self.assertFalse(self.cache.exists())


if __name__ == "__main__":
    unittest.main()
