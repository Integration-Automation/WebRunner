import unittest
from unittest.mock import MagicMock, patch

from je_web_runner.utils.notifier.webhook_notifier import (
    NotifierError,
    notify_run_summary,
    notify_slack,
    notify_webhook,
    summarise_run,
)
from je_web_runner.utils.test_record.test_record_class import (
    record_action_to_list,
    test_record_instance,
)


class TestSummariseRun(unittest.TestCase):

    def setUp(self):
        test_record_instance.clean_record()
        self._original = test_record_instance.init_record
        test_record_instance.init_record = True

    def tearDown(self):
        test_record_instance.clean_record()
        test_record_instance.init_record = self._original

    def test_empty_records_summary(self):
        summary = summarise_run()
        self.assertEqual(summary, {"total": 0, "passed": 0, "failed": 0, "failures": []})

    def test_mixed_records_summary(self):
        record_action_to_list("ok", None, None)
        record_action_to_list("bad", None, RuntimeError("boom"))
        summary = summarise_run()
        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["passed"], 1)
        self.assertEqual(summary["failed"], 1)
        self.assertEqual(summary["failures"][0]["function_name"], "bad")


class TestWebhook(unittest.TestCase):

    def test_url_must_be_http(self):
        with self.assertRaises(NotifierError):
            notify_webhook("ftp://example.com", {})  # NOSONAR — fixture, asserts the validator rejects it

    def test_post_with_payload_returns_status(self):
        response = MagicMock(status_code=200, text="ok")
        with patch("je_web_runner.utils.notifier.webhook_notifier.requests.post",
                   return_value=response) as post_mock:
            status = notify_webhook("https://example.com/hook", {"a": 1})
            self.assertEqual(status, 200)
            post_mock.assert_called_once()
            self.assertEqual(post_mock.call_args.kwargs["json"], {"a": 1})

    def test_error_status_raises(self):
        response = MagicMock(status_code=500, text="boom")
        with patch("je_web_runner.utils.notifier.webhook_notifier.requests.post",
                   return_value=response):
            with self.assertRaises(NotifierError):
                notify_webhook("https://example.com/hook", {})


class TestSlack(unittest.TestCase):

    def setUp(self):
        test_record_instance.clean_record()
        self._original = test_record_instance.init_record
        test_record_instance.init_record = True

    def tearDown(self):
        test_record_instance.clean_record()
        test_record_instance.init_record = self._original

    def test_notify_slack_formats_summary(self):
        record_action_to_list("ok", None, None)
        record_action_to_list("bad", None, RuntimeError("kaboom"))
        response = MagicMock(status_code=200, text="ok")
        with patch("je_web_runner.utils.notifier.webhook_notifier.requests.post",
                   return_value=response) as post_mock:
            notify_slack("https://hooks.slack.com/services/x")
            payload = post_mock.call_args.kwargs["json"]
            self.assertIn("text", payload)
            self.assertIn("total: 2", payload["text"])
            self.assertIn("kaboom", payload["text"])

    def test_notify_run_summary_passes_through(self):
        response = MagicMock(status_code=200, text="ok")
        with patch("je_web_runner.utils.notifier.webhook_notifier.requests.post",
                   return_value=response):
            self.assertEqual(notify_run_summary("https://example.com/hook"), 200)


if __name__ == "__main__":
    unittest.main()
