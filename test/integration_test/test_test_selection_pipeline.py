"""
Integration: coverage_map + impact_analysis + diff_shard wired together.

Builds a fake action-tree, simulates a git diff, and confirms the three
selection layers agree on which tests to run.
"""
import json
import tempfile
import unittest
from pathlib import Path

from je_web_runner.utils.coverage_map.coverage import (
    build_coverage_map,
)
from je_web_runner.utils.impact_analysis.indexer import (
    affected_action_files,
    build_index,
)
from je_web_runner.utils.sharding.diff_shard import select_action_files


def _write_actions(path: Path, actions):
    path.write_text(json.dumps(actions), encoding="utf-8")


class TestTestSelectionPipeline(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)
        self.login = self.root / "actions" / "login.json"
        self.checkout = self.root / "actions" / "checkout.json"
        self.search = self.root / "actions" / "search.json"
        self.login.parent.mkdir(parents=True)
        _write_actions(self.login, [
            ["WR_to_url", {"url": "https://example.com/auth/login"}],
            ["WR_save_test_object", {"test_object_name": "submit",
                                     "object_type": "ID"}],
            ["WR_find_recorded_element", {"element_name": "submit"}],
            ["WR_element_click"],
        ])
        _write_actions(self.checkout, [
            ["WR_to_url", {"url": "https://example.com/checkout/cart/42"}],
            ["WR_save_test_object", {"test_object_name": "buy",
                                     "object_type": "ID"}],
        ])
        _write_actions(self.search, [
            ["WR_to_url", {"url": "https://example.com/search?q=anything"}],
        ])

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_coverage_map_lists_routes(self):
        coverage = build_coverage_map(self.root / "actions")
        self.assertEqual(coverage.files_for("/auth/login"), [str(self.login)])
        # Numeric segments collapse to ``:id`` so cart/42 lands under
        # /checkout/cart/:id.
        self.assertEqual(coverage.files_for("/checkout/cart/:id"),
                         [str(self.checkout)])
        # Uncovered route returns []
        self.assertEqual(coverage.files_for("/admin"), [])

    def test_impact_analysis_finds_locator_consumers(self):
        index = build_index(self.root / "actions")
        # ``submit`` locator changed → only login.json is affected.
        affected = affected_action_files(index, locators=["submit"])
        self.assertEqual(affected, [str(self.login)])

    def test_diff_shard_filters_by_changed_paths(self):
        candidates = [str(self.login), str(self.checkout), str(self.search)]
        # Simulate a git diff that only touched checkout.json
        selected = select_action_files(
            candidates, [str(self.checkout)],
        )
        self.assertEqual(selected, [str(self.checkout)])

    def test_pipeline_combined_query(self):
        coverage = build_coverage_map(self.root / "actions")
        index = build_index(self.root / "actions")
        # Suppose "submit" locator + "/auth/" route + checkout.json all
        # changed in the same PR. Final to-run set is the union.
        from_locator = set(affected_action_files(index, locators=["submit"]))
        from_url = set(coverage.files_for("/auth/login"))
        from_diff = set(select_action_files(
            [str(self.login), str(self.checkout), str(self.search)],
            [str(self.checkout)],
        ))
        to_run = from_locator | from_url | from_diff
        self.assertEqual(to_run, {str(self.login), str(self.checkout)})


if __name__ == "__main__":
    unittest.main()
