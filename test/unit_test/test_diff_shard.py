import unittest

from je_web_runner.utils.sharding.diff_shard import (
    DiffShardError,
    changed_paths,
    select_action_files,
    select_for_changed,
)


def _runner_returning(text):
    def runner(args):
        return text
    return runner


def _runner_raising():
    def runner(args):
        raise DiffShardError("boom")
    return runner


class TestChangedPaths(unittest.TestCase):

    def test_parses_lines(self):
        paths = changed_paths(
            git_runner=_runner_returning("a/b.json\n c/d.json\n\n"),
        )
        self.assertEqual(paths, ["a/b.json", "c/d.json"])

    def test_runner_failure_propagates(self):
        with self.assertRaises(DiffShardError):
            changed_paths(git_runner=_runner_raising())


class TestSelect(unittest.TestCase):

    def test_keeps_only_changed(self):
        candidates = ["actions/a.json", "actions/b.json", "actions/c.json"]
        selected = select_action_files(candidates, ["actions/b.json"])
        self.assertEqual(selected, ["actions/b.json"])

    def test_normalises_separators(self):
        candidates = ["actions\\a.json"]
        selected = select_action_files(candidates, ["actions/a.json"])
        self.assertEqual(selected, ["actions\\a.json"])

    def test_additional_keep(self):
        candidates = ["actions/a.json", "actions/core.json"]
        selected = select_action_files(
            candidates, ["actions/a.json"],
            additional_keep=["actions/core.json"],
        )
        self.assertEqual(selected, ["actions/a.json", "actions/core.json"])


class TestSelectForChanged(unittest.TestCase):

    def test_pipeline(self):
        runner = _runner_returning("actions/x.json\n")
        result = select_for_changed(
            ["actions/x.json", "actions/y.json"],
            git_runner=runner,
        )
        self.assertEqual(result, ["actions/x.json"])


if __name__ == "__main__":
    unittest.main()
