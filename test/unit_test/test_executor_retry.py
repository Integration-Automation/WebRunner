import unittest
from unittest.mock import patch

from je_web_runner.utils.executor.action_executor import Executor


class TestExecutorRetry(unittest.TestCase):

    def test_default_policy_disables_retry(self):
        executor = Executor()
        attempts = {"n": 0}

        def flaky():
            attempts["n"] += 1
            raise RuntimeError("boom")

        executor.event_dict["WR_test_flaky"] = flaky
        with self.assertRaises(RuntimeError):
            executor._execute_with_retry(["WR_test_flaky"])
        self.assertEqual(attempts["n"], 1)

    def test_retries_then_succeeds(self):
        executor = Executor()
        executor.set_retry_policy(retries=2, backoff=0.0)
        attempts = {"n": 0}

        def flaky():
            attempts["n"] += 1
            if attempts["n"] < 3:
                raise RuntimeError("boom")
            return "ok"

        executor.event_dict["WR_test_flaky"] = flaky
        result = executor._execute_with_retry(["WR_test_flaky"])
        self.assertEqual(result, "ok")
        self.assertEqual(attempts["n"], 3)

    def test_retries_exhausted_raises_last_error(self):
        executor = Executor()
        executor.set_retry_policy(retries=2)

        def always_fails():
            raise ValueError("nope")

        executor.event_dict["WR_test_fail"] = always_fails
        with self.assertRaises(ValueError):
            executor._execute_with_retry(["WR_test_fail"])

    def test_backoff_sleep_called_between_attempts(self):
        executor = Executor()
        executor.set_retry_policy(retries=2, backoff=0.5)

        def always_fails():
            raise RuntimeError("boom")

        executor.event_dict["WR_test_fail"] = always_fails
        with patch("je_web_runner.utils.executor.action_executor.time.sleep") as sleep_mock, \
                self.assertRaises(RuntimeError):
            executor._execute_with_retry(["WR_test_fail"])
        # backoff(0.5) * (1, 2) → 0.5 + 1.0
        self.assertEqual(sleep_mock.call_args_list[0][0][0], 0.5)
        self.assertEqual(sleep_mock.call_args_list[1][0][0], 1.0)

    def test_set_retry_policy_clamps_negatives(self):
        executor = Executor()
        executor.set_retry_policy(retries=-3, backoff=-1.0)
        self.assertEqual(executor.retry_policy["retries"], 0)
        self.assertEqual(executor.retry_policy["backoff"], 0.0)

    def test_execute_action_uses_retry_layer(self):
        executor = Executor()
        executor.set_retry_policy(retries=1, backoff=0.0)
        attempts = {"n": 0}

        def flaky():
            attempts["n"] += 1
            if attempts["n"] < 2:
                raise RuntimeError("boom")
            return "ok"

        executor.event_dict["WR_test_action"] = flaky
        result = executor.execute_action([["WR_test_action"]])
        self.assertEqual(list(result.values()), ["ok"])
        self.assertEqual(attempts["n"], 2)


if __name__ == "__main__":
    unittest.main()
