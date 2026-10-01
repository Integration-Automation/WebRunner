"""Which files ``-d DIR`` runs: tags, shards, re-running failures (and their combinations)."""
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from je_web_runner.utils.cli.cli_main import main
from je_web_runner.utils.run_ledger.ledger import record_run


def _write(directory: str, name: str, actions, tags=None) -> str:
    path = os.path.join(directory, name)
    payload = {"meta": {"tags": tags}, "webdriver_wrapper": actions} if tags is not None else actions
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)
    return os.path.abspath(path)


class TestFileSelection(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = tmp.name
        self.smoke = _write(self.dir, "smoke.json", [["WR_quit"]], tags=["smoke"])
        self.slow = _write(self.dir, "slow.json", [["WR_quit"]], tags=["slow"])
        self.plain = _write(self.dir, "plain.json", [["WR_quit"]])

    def _ran(self, *flags) -> list:
        with patch("je_web_runner.utils.cli.cli_main.execute_files") as run:
            main(["-d", self.dir, *flags])
        return sorted(run.call_args.args[0]) if run.called else []

    def test_everything_without_filters(self):
        self.assertEqual(self._ran(), sorted([self.smoke, self.slow, self.plain]))

    def test_tags(self):
        self.assertEqual(self._ran("--tag", "smoke"), [self.smoke])
        self.assertEqual(self._ran("--exclude-tag", "slow"), sorted([self.smoke, self.plain]))

    def test_shards_cover_every_file_once(self):
        first, second = self._ran("--shard", "1/2"), self._ran("--shard", "2/2")
        self.assertEqual(sorted(first + second), sorted([self.smoke, self.slow, self.plain]))
        self.assertFalse(set(first) & set(second))

    def test_rerun_failed_runs_only_the_failures(self):
        ledger = os.path.join(self.dir, "ledger.out")
        record_run(ledger, self.slow, passed=False)
        record_run(ledger, self.smoke, passed=True)
        self.assertEqual(self._ran("--rerun-failed", ledger), [self.slow])


if __name__ == "__main__":
    unittest.main()
