"""Unit tests for je_web_runner.utils.commit_msg_trigger."""
import unittest

from je_web_runner.utils.commit_msg_trigger.trigger import (
    CommitMsgTriggerError,
    TriggerPlan,
    assert_no_skip,
    assigned_shard,
    parse,
    should_run_job,
)


class TestParse(unittest.TestCase):

    def test_skip_ci(self):
        self.assertTrue(parse("docs: typo [skip ci]").skip)
        self.assertTrue(parse("docs [ci skip]").skip)
        self.assertTrue(parse("docs [no-ci]").skip)

    def test_bucket(self):
        p = parse("fix: bug [ci e2e]")
        self.assertIn("e2e", p.only_buckets)

    def test_multi_bucket(self):
        p = parse("[ci e2e] [ci unit]")
        self.assertEqual(p.only_buckets, {"e2e", "unit"})

    def test_shard(self):
        p = parse("scale [ci shard=3/8]")
        self.assertEqual(p.shard, (3, 8))

    def test_bad_shard(self):
        with self.assertRaises(CommitMsgTriggerError):
            parse("scale [ci shard=9/8]")

    def test_label(self):
        p = parse("perf check [smoke] [nightly]")
        self.assertEqual(p.labels, {"smoke", "nightly"})

    def test_tickets(self):
        p = parse("Closes #123 and fixes ABC-456")
        self.assertEqual(p.tickets, {"#123", "ABC-456"})

    def test_no_specials(self):
        p = parse("plain message")
        self.assertFalse(p.skip)
        self.assertEqual(p.only_buckets, set())
        self.assertEqual(p.labels, set())
        self.assertIsNone(p.shard)

    def test_bad_type(self):
        with self.assertRaises(CommitMsgTriggerError):
            parse(123)


class TestShouldRunJob(unittest.TestCase):

    def test_skip(self):
        self.assertFalse(should_run_job(TriggerPlan(skip=True), "e2e"))

    def test_only_match(self):
        self.assertTrue(
            should_run_job(TriggerPlan(only_buckets={"e2e"}), "e2e"),
        )

    def test_only_mismatch(self):
        self.assertFalse(
            should_run_job(TriggerPlan(only_buckets={"e2e"}), "unit"),
        )

    def test_no_constraints(self):
        self.assertTrue(should_run_job(TriggerPlan(), "any"))

    def test_empty_job(self):
        with self.assertRaises(CommitMsgTriggerError):
            should_run_job(TriggerPlan(), "")


class TestShard(unittest.TestCase):

    def test_no_override(self):
        self.assertIsNone(assigned_shard(TriggerPlan(), total_shards=8))

    def test_match(self):
        self.assertEqual(
            assigned_shard(TriggerPlan(shard=(3, 8)), total_shards=8), 2,
        )

    def test_mismatch_total(self):
        with self.assertRaises(CommitMsgTriggerError):
            assigned_shard(TriggerPlan(shard=(3, 8)), total_shards=4)

    def test_bad_total(self):
        with self.assertRaises(CommitMsgTriggerError):
            assigned_shard(TriggerPlan(), total_shards=0)


class TestAssertNoSkip(unittest.TestCase):

    def test_pass(self):
        assert_no_skip(TriggerPlan())

    def test_fail(self):
        with self.assertRaises(CommitMsgTriggerError):
            assert_no_skip(TriggerPlan(skip=True))


if __name__ == "__main__":
    unittest.main()
