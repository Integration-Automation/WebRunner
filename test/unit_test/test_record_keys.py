"""A repeated action keeps every result: ``key``, ``key #2`` … (as AutoControl's ``_unique_key``)."""
import asyncio
import unittest
from unittest.mock import MagicMock

from je_web_runner.utils.async_executor.executor import AsyncExecutor
from je_web_runner.utils.executor.action_executor import Executor, unique_record_key


class TestUniqueRecordKey(unittest.TestCase):

    def test_first_keeps_the_bare_key_and_repeats_are_numbered(self):
        record = {}
        for value in range(3):
            record[unique_record_key(record, "execute: ['WR_x']")] = value
        self.assertEqual(record, {"execute: ['WR_x']": 0, "execute: ['WR_x'] #2": 1, "execute: ['WR_x'] #3": 2})


class TestRepeatedActions(unittest.TestCase):

    def setUp(self):
        self.executor = Executor()
        self.executor.event_dict["WR_click"] = MagicMock(side_effect=[RuntimeError("not clickable yet"), "clicked"])

    def test_both_outcomes_are_kept_and_failed_names_the_failed_one(self):
        record, failed = self.executor.collect_action_results([["WR_click"], ["len", [[1]]], ["WR_click"]])
        self.assertEqual(list(record), ["execute: ['WR_click']", "execute: ['len', [[1]]]", "execute: ['WR_click'] #2"])
        self.assertEqual(failed, ["execute: ['WR_click']"])
        self.assertIn("not clickable yet", record[failed[0]])
        self.assertEqual(record["execute: ['WR_click'] #2"], "clicked")

    def test_the_async_executor_does_the_same(self):
        runner = AsyncExecutor(sync=self.executor)
        record, failed = asyncio.run(runner.run([["WR_click"], ["WR_click"]]))
        self.assertEqual(failed, ["execute: ['WR_click']"])
        self.assertEqual(record["execute: ['WR_click'] #2"], "clicked")


if __name__ == "__main__":
    unittest.main()
