"""Unit tests for je_web_runner.utils.webhook_signature_verify."""
import time
import unittest

from je_web_runner.utils.webhook_signature_verify.verify import (
    Scheme,
    WebhookSignatureVerifyError,
    assert_valid,
    sign_github,
    sign_slack,
    sign_stripe,
    verify,
)


class TestGithub(unittest.TestCase):

    def test_pass(self):
        body = b'{"x":1}'
        headers = {"X-Hub-Signature-256": sign_github(body, "sec")}
        self.assertTrue(verify(Scheme.GITHUB, headers, body, "sec").ok)

    def test_tampered_body(self):
        body = b'{"x":1}'
        headers = {"X-Hub-Signature-256": sign_github(body, "sec")}
        tampered = b'{"x":2}'
        self.assertFalse(verify(Scheme.GITHUB, headers, tampered, "sec").ok)

    def test_missing_header(self):
        with self.assertRaises(WebhookSignatureVerifyError):
            verify(Scheme.GITHUB, {}, b"", "sec")

    def test_bad_prefix(self):
        with self.assertRaises(WebhookSignatureVerifyError):
            verify(Scheme.GITHUB, {"X-Hub-Signature-256": "abc"}, b"", "sec")


class TestStripe(unittest.TestCase):

    def test_pass(self):
        body = b"payload"
        headers = {"Stripe-Signature": sign_stripe(body, "sec")}
        self.assertTrue(verify(Scheme.STRIPE, headers, body, "sec").ok)

    def test_old_timestamp_rejected(self):
        body = b"payload"
        headers = {"Stripe-Signature": sign_stripe(body, "sec",
                                                   ts=int(time.time()) - 9999)}
        with self.assertRaises(WebhookSignatureVerifyError):
            verify(Scheme.STRIPE, headers, body, "sec")

    def test_missing_components(self):
        with self.assertRaises(WebhookSignatureVerifyError):
            verify(Scheme.STRIPE, {"Stripe-Signature": "x=y"}, b"", "sec")

    def test_bad_ts(self):
        with self.assertRaises(WebhookSignatureVerifyError):
            verify(Scheme.STRIPE,
                   {"Stripe-Signature": "t=abc,v1=def"}, b"", "sec")


class TestSlack(unittest.TestCase):

    def test_pass(self):
        body = b"q=1"
        ts = int(time.time())
        headers = {
            "X-Slack-Signature": sign_slack(body, "sec", ts=ts),
            "X-Slack-Request-Timestamp": str(ts),
        }
        self.assertTrue(verify(Scheme.SLACK, headers, body, "sec").ok)

    def test_replay_rejected(self):
        body = b"q=1"
        ts = int(time.time()) - 99999
        headers = {
            "X-Slack-Signature": sign_slack(body, "sec", ts=ts),
            "X-Slack-Request-Timestamp": str(ts),
        }
        with self.assertRaises(WebhookSignatureVerifyError):
            verify(Scheme.SLACK, headers, body, "sec")

    def test_missing(self):
        with self.assertRaises(WebhookSignatureVerifyError):
            verify(Scheme.SLACK, {}, b"", "sec")


class TestGeneric(unittest.TestCase):

    def test_pass(self):
        import hmac
        import hashlib
        body = b"x"
        sig = hmac.new(b"sec", body, hashlib.sha256).hexdigest()
        self.assertTrue(verify(Scheme.GENERIC, {"X-Signature": sig}, body,
                               "sec").ok)

    def test_missing(self):
        with self.assertRaises(WebhookSignatureVerifyError):
            verify(Scheme.GENERIC, {}, b"x", "sec")


class TestInputValidation(unittest.TestCase):

    def test_bad_scheme(self):
        with self.assertRaises(WebhookSignatureVerifyError):
            verify("github", {}, b"", "x")

    def test_bad_headers(self):
        with self.assertRaises(WebhookSignatureVerifyError):
            verify(Scheme.GENERIC, "nope", b"", "x")

    def test_bad_body(self):
        with self.assertRaises(WebhookSignatureVerifyError):
            verify(Scheme.GENERIC, {}, "str", "x")

    def test_bad_secret(self):
        with self.assertRaises(WebhookSignatureVerifyError):
            verify(Scheme.GENERIC, {}, b"", "")


class TestAssertValid(unittest.TestCase):

    def test_pass(self):
        body = b"x"
        result = verify(Scheme.GITHUB,
                        {"X-Hub-Signature-256": sign_github(body, "sec")},
                        body, "sec")
        assert_valid(result)

    def test_fail(self):
        result = verify(Scheme.GITHUB,
                        {"X-Hub-Signature-256": "sha256=" + "0" * 64},
                        b"x", "sec")
        with self.assertRaises(WebhookSignatureVerifyError):
            assert_valid(result)


if __name__ == "__main__":
    unittest.main()
