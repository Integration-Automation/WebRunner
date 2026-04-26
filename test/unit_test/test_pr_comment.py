import io
import json
import unittest
from unittest.mock import patch

from je_web_runner.utils.pr_comment import (
    PrCommentError,
    PrSummary,
    build_summary_markdown,
    post_or_update_comment,
)


def _fake_response(payload):
    body = json.dumps(payload).encode("utf-8")
    fake = io.BytesIO(body)
    fake.__enter__ = lambda self=fake: self
    fake.__exit__ = lambda *a: None
    return fake


class TestSummaryMarkdown(unittest.TestCase):

    def test_includes_marker_and_counts(self):
        text = build_summary_markdown(PrSummary(total=10, passed=8, failed=1, skipped=1))
        self.assertIn("<!-- webrunner-summary -->", text)
        self.assertIn("**Total:** 10", text)
        self.assertIn("**Passed:** 8", text)

    def test_run_url_link(self):
        text = build_summary_markdown(
            PrSummary(total=1, passed=1, failed=0),
            run_url="https://example.com/run/1",
        )
        self.assertIn("https://example.com/run/1", text)


class TestPostOrUpdate(unittest.TestCase):

    def test_creates_new_when_marker_absent(self):
        sequence = [
            _fake_response([{"id": 1, "body": "no marker"}]),  # list comments
            _fake_response({"id": 99, "body": "ok"}),  # POST
        ]
        with patch(
            "je_web_runner.utils.pr_comment.poster.urllib.request.urlopen",
            side_effect=sequence,
        ) as urlopen_mock:
            result = post_or_update_comment(
                "owner/repo", 42, "hello",
                token="secret",  # nosec B106 — fake test fixture
            )
        self.assertEqual(result["id"], 99)
        # last call should have been a POST to the comments URL
        _request = urlopen_mock.call_args.args[0]
        self.assertEqual(_request.method, "POST")
        self.assertIn("/issues/42/comments", _request.full_url)

    def test_patches_existing_marker(self):
        sequence = [
            _fake_response([{"id": 7, "body": "<!-- webrunner-summary -->\nold"}]),
            _fake_response({"id": 7, "body": "new"}),
        ]
        with patch(
            "je_web_runner.utils.pr_comment.poster.urllib.request.urlopen",
            side_effect=sequence,
        ) as urlopen_mock:
            post_or_update_comment(
                "owner/repo", 1, "new body",
                token="t",  # nosec B106 — fake test fixture
            )
        last = urlopen_mock.call_args.args[0]
        self.assertEqual(last.method, "PATCH")
        self.assertIn("/issues/comments/7", last.full_url)

    def test_missing_token_raises(self):
        with self.assertRaises(PrCommentError):
            post_or_update_comment("owner/repo", 1, "body", token=None)

    def test_bad_repo_raises(self):
        with self.assertRaises(PrCommentError):
            post_or_update_comment(
                "single-segment", 1, "body",
                token="t",  # nosec B106 — fake test fixture
            )


if __name__ == "__main__":
    unittest.main()
