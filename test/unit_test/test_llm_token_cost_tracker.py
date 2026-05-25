"""Unit tests for je_web_runner.utils.llm_token_cost_tracker."""
import unittest

from je_web_runner.utils.llm_token_cost_tracker.tracker import (
    CallRecord,
    LlmTokenCostError,
    Tally,
    assert_under_budget,
    compute_cost,
    tally,
    tally_by_test,
    top_spenders,
)


class TestRecord(unittest.TestCase):

    def test_basic(self):
        r = CallRecord(model="claude-opus-4-7", input_tokens=100,
                       output_tokens=100)
        self.assertEqual(r.model, "claude-opus-4-7")

    def test_empty_model(self):
        with self.assertRaises(LlmTokenCostError):
            CallRecord(model="")

    def test_negative(self):
        with self.assertRaises(LlmTokenCostError):
            CallRecord(model="x", input_tokens=-1)


class TestCompute(unittest.TestCase):

    def test_known_model(self):
        cost = compute_cost(CallRecord(model="claude-haiku-4-5",
                                       input_tokens=1000,
                                       output_tokens=1000))
        # 0.001 + 0.005
        self.assertAlmostEqual(cost, 0.006, places=6)

    def test_prefix_match(self):
        cost = compute_cost(CallRecord(
            model="claude-opus-4-7-2026-05-01",
            input_tokens=1000, output_tokens=1000,
        ))
        # uses claude-opus-4-7 prices: 0.015 + 0.075
        self.assertAlmostEqual(cost, 0.090, places=6)

    def test_unknown_model(self):
        with self.assertRaises(LlmTokenCostError):
            compute_cost(CallRecord(model="weird-model"))

    def test_override(self):
        cost = compute_cost(
            CallRecord(model="my-model", input_tokens=1000),
            rate_card_override={"my-model": {"input": 0.1, "output": 0}},
        )
        self.assertAlmostEqual(cost, 0.1, places=6)


class TestTally(unittest.TestCase):

    def test_aggregate(self):
        summary = tally([
            CallRecord(model="claude-haiku-4-5", input_tokens=1000),
            CallRecord(model="claude-haiku-4-5", output_tokens=1000),
        ])
        self.assertEqual(summary.calls, 2)
        self.assertAlmostEqual(summary.cost_usd, 0.006, places=6)

    def test_bad_record(self):
        with self.assertRaises(LlmTokenCostError):
            tally(["nope"])


class TestByTest(unittest.TestCase):

    def test_buckets(self):
        out = tally_by_test([
            CallRecord(model="claude-haiku-4-5", input_tokens=1000,
                       test_name="t1"),
            CallRecord(model="claude-haiku-4-5", input_tokens=1000,
                       test_name="t2"),
        ])
        self.assertIn("t1", out)
        self.assertIn("t2", out)

    def test_unknown_bucket(self):
        out = tally_by_test([CallRecord(model="claude-haiku-4-5",
                                        input_tokens=10)])
        self.assertIn("(unknown)", out)


class TestBudget(unittest.TestCase):

    def test_pass(self):
        assert_under_budget(Tally(cost_usd=0.5), max_usd=1.0)

    def test_fail(self):
        with self.assertRaises(LlmTokenCostError):
            assert_under_budget(Tally(cost_usd=2), max_usd=1)

    def test_bad_max(self):
        with self.assertRaises(LlmTokenCostError):
            assert_under_budget(Tally(), max_usd=0)


class TestTopSpenders(unittest.TestCase):

    def test_sorted(self):
        out = top_spenders(
            {"a": Tally(cost_usd=0.1), "b": Tally(cost_usd=1.0)},
            top_n=2,
        )
        self.assertEqual(out[0]["test"], "b")

    def test_bad_n(self):
        with self.assertRaises(LlmTokenCostError):
            top_spenders({}, top_n=0)


if __name__ == "__main__":
    unittest.main()
