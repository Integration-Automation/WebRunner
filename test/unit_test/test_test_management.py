import unittest
from unittest.mock import MagicMock, patch

from je_web_runner.utils.test_management.jira_client import (
    JiraError,
    jira_create_failure_issues,
    jira_create_issue,
)
from je_web_runner.utils.test_record.test_record_class import (
    record_action_to_list,
    test_record_instance,
)


class TestJiraCreateIssue(unittest.TestCase):

    def test_invalid_url_raises(self):
        with self.assertRaises(JiraError):
            jira_create_issue("ftp://x", "u", "k", "P", "summary")  # NOSONAR — fixture, asserts the validator rejects it

    def test_posts_expected_payload(self):
        response = MagicMock(status_code=201, text="ok")
        response.json.return_value = {"key": "P-1"}
        with patch("je_web_runner.utils.test_management.jira_client.requests.post",
                   return_value=response) as post_mock:
            result = jira_create_issue(
                "https://example.atlassian.net",
                "alice@example.com",
                "token",
                "PROJ",
                summary="boom",
                description="details",
            )
            self.assertEqual(result, {"key": "P-1"})
            payload = post_mock.call_args.kwargs["json"]
            self.assertEqual(payload["fields"]["project"]["key"], "PROJ")
            self.assertEqual(payload["fields"]["summary"], "boom")
            self.assertEqual(payload["fields"]["issuetype"]["name"], "Bug")

    def test_error_status_raises(self):
        response = MagicMock(status_code=500, text="boom")
        with patch("je_web_runner.utils.test_management.jira_client.requests.post",
                   return_value=response):
            with self.assertRaises(JiraError):
                jira_create_issue("https://x", "u", "k", "P", "s")


class TestJiraCreateFailureIssues(unittest.TestCase):

    def setUp(self):
        test_record_instance.clean_record()
        self._original = test_record_instance.init_record
        test_record_instance.init_record = True

    def tearDown(self):
        test_record_instance.clean_record()
        test_record_instance.init_record = self._original

    def test_one_issue_per_failure(self):
        record_action_to_list("step1", None, None)
        record_action_to_list("step2", None, RuntimeError("boom"))
        record_action_to_list("step3", None, ValueError("nope"))
        response = MagicMock(status_code=201, text="ok")
        response.json.return_value = {"key": "X"}
        with patch("je_web_runner.utils.test_management.jira_client.requests.post",
                   return_value=response) as post_mock:
            issues = jira_create_failure_issues(
                "https://example.atlassian.net", "u", "k", "PROJ", build_url="https://ci",
            )
            self.assertEqual(len(issues), 2)
            self.assertEqual(post_mock.call_count, 2)


if __name__ == "__main__":
    unittest.main()
