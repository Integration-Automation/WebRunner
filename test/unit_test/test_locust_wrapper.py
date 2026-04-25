import sys
import unittest
from unittest.mock import MagicMock, patch

from je_web_runner.utils.load_test.locust_wrapper import (
    LoadTestError,
    _build_task,
    build_http_user_class,
    run_locust,
)


class TestBuildTask(unittest.TestCase):

    def test_task_invokes_request_with_method_and_path(self):
        task_fn = _build_task({
            "name": "list users",
            "method": "GET",
            "path": "/api/users",
            "headers": {"X": "1"},
            "params": {"page": 1},
        })
        client = MagicMock()
        instance = MagicMock(client=client)
        task_fn(instance)
        kwargs = client.request.call_args.kwargs
        self.assertEqual(client.request.call_args.args, ("GET", "/api/users"))
        self.assertEqual(kwargs["name"], "list users")
        self.assertEqual(kwargs["headers"], {"X": "1"})
        self.assertEqual(kwargs["params"], {"page": 1})

    def test_post_with_json_body(self):
        task_fn = _build_task({"method": "POST", "path": "/x", "json_body": {"a": 1}})
        client = MagicMock()
        task_fn(MagicMock(client=client))
        kwargs = client.request.call_args.kwargs
        self.assertEqual(client.request.call_args.args, ("POST", "/x"))
        self.assertEqual(kwargs["json"], {"a": 1})


class TestBuildUserClass(unittest.TestCase):

    def test_missing_locust_raises_helpful_error(self):
        with patch.dict(sys.modules, {"locust": None, "locust.env": None}):
            with self.assertRaises(LoadTestError) as ctx:
                build_http_user_class([{"method": "GET", "path": "/"}])
            self.assertIn("pip install locust", str(ctx.exception))

    def test_user_class_has_one_task_per_action(self):
        # Mock the locust import so this test does not drag gevent's monkey
        # patches in (broken on Python 3.14).
        class FakeUserMeta(type):
            pass

        class FakeUser(metaclass=FakeUserMeta):
            pass

        def fake_task(weight):
            def wrap(func):
                func._weight = weight
                return func
            return wrap

        with patch(
            "je_web_runner.utils.load_test.locust_wrapper._require_locust",
            return_value=(FakeUser, lambda lo, hi: (lo, hi), fake_task, MagicMock()),
        ):
            actions = [
                {"name": "list", "method": "GET", "path": "/u", "weight": 5},
                {"name": "create", "method": "POST", "path": "/u", "weight": 1},
            ]
            cls = build_http_user_class(actions)
            self.assertTrue(hasattr(cls, "task_0"))
            self.assertTrue(hasattr(cls, "task_1"))
            self.assertEqual(cls.task_0._weight, 5)
            self.assertEqual(cls.task_1._weight, 1)


class TestRunLocust(unittest.TestCase):

    def test_invalid_host_rejected(self):
        with self.assertRaises(LoadTestError):
            run_locust("ftp://x", actions=[{"method": "GET", "path": "/"}])

    def test_runs_environment_and_summarises(self):
        # Build minimal stub objects that mimic locust's stats shape.
        stats_entry = MagicMock(
            name="GET /u", method="GET",
            num_requests=10, num_failures=1,
            median_response_time=12.0, avg_response_time=15.0, current_rps=4.0,
        )
        stats_entry.name = "GET /u"
        total = MagicMock(num_requests=10, num_failures=1, median_response_time=12.0, avg_response_time=15.0)
        stats = MagicMock(total=total, entries={("GET", "/u"): stats_entry})

        runner = MagicMock()
        env = MagicMock()
        env.create_local_runner.return_value = runner
        env.stats = stats

        environment_class = MagicMock(return_value=env)
        with patch(
            "je_web_runner.utils.load_test.locust_wrapper._require_locust",
            return_value=(MagicMock(), MagicMock(), lambda weight=1: (lambda f: f), environment_class),
        ), patch("je_web_runner.utils.load_test.locust_wrapper.time.sleep"):
            result = run_locust(
                "https://example.com",
                actions=[{"method": "GET", "path": "/u"}],
                num_users=2,
                spawn_rate=1,
                run_seconds=0,
            )
        runner.start.assert_called_once_with(2, spawn_rate=1)
        runner.stop.assert_called_once()
        self.assertEqual(result["total"]["num_requests"], 10)
        self.assertEqual(len(result["per_endpoint"]), 1)


if __name__ == "__main__":
    unittest.main()
