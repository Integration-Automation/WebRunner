import unittest
from unittest.mock import MagicMock

from je_web_runner.utils.adaptive_retry import (
    AdaptiveRetryError,
    RetryPolicy,
    run_with_retry,
)
from je_web_runner.utils.adaptive_retry.policy import summarise_history


class TestRunWithRetry(unittest.TestCase):

    def test_returns_first_success_without_retry(self):
        func = MagicMock(return_value="ok")
        policy = RetryPolicy()
        result = run_with_retry(func, policy=policy)
        self.assertEqual(result, "ok")
        self.assertEqual(func.call_count, 1)
        self.assertEqual(policy.history, [])

    def test_retries_transient_until_success(self):
        attempts = {"n": 0}

        def flaky_call():
            attempts["n"] += 1
            if attempts["n"] < 3:
                raise TimeoutError("retry me")
            return "done"

        sleeps = []
        policy = RetryPolicy(base_backoff=0.01, max_backoff=0.05)
        result = run_with_retry(flaky_call, policy=policy, sleep=sleeps.append)
        self.assertEqual(result, "done")
        self.assertEqual(attempts["n"], 3)
        self.assertEqual(len(policy.history), 2)
        self.assertTrue(all(d.category == "transient" for d in policy.history))
        self.assertEqual(len(sleeps), 2)

    def test_real_failure_raises_adaptive_retry_error(self):
        def bad():
            raise ValueError("a bug")

        policy = RetryPolicy()
        with self.assertRaises(AdaptiveRetryError):
            run_with_retry(bad, policy=policy, sleep=lambda _s: None)
        self.assertEqual(len(policy.history), 1)
        self.assertEqual(policy.history[0].category, "real")

    def test_flaky_classification_uses_ledger(self):
        attempts = {"n": 0}

        def call():
            attempts["n"] += 1
            raise ValueError("not a real bug")

        # Stub the ledger lookup so the path is treated as flaky
        from je_web_runner.utils.run_ledger import classifier as cls_mod
        original = cls_mod.flaky_paths
        cls_mod.flaky_paths = lambda _path: {"the_test.py"}
        try:
            policy = RetryPolicy(flaky_max=2)
            with self.assertRaises(ValueError):
                run_with_retry(
                    call,
                    policy=policy,
                    ledger_path="ledger.json",
                    file_path="the_test.py",
                    sleep=lambda _s: None,
                )
        finally:
            cls_mod.flaky_paths = original
        self.assertEqual(attempts["n"], 3)
        self.assertTrue(all(d.category == "flaky" for d in policy.history))

    def test_summary_aggregates_categories(self):
        def fail():
            raise TimeoutError("slow")

        policy = RetryPolicy(transient_max=2, base_backoff=0)
        with self.assertRaises(TimeoutError):
            run_with_retry(fail, policy=policy, sleep=lambda _s: None)
        summary = summarise_history(policy)
        self.assertEqual(summary["attempts"], 3)
        self.assertEqual(summary["by_category"]["transient"], 3)


if __name__ == "__main__":
    unittest.main()
