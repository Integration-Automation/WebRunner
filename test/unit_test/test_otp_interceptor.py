"""Unit tests for je_web_runner.utils.otp_interceptor."""
import time
import unittest
from unittest.mock import MagicMock

from je_web_runner.utils.otp_interceptor.interceptor import (
    InMemoryProvider,
    InterceptedMessage,
    MailHogProvider,
    MailpitProvider,
    OtpInterceptError,
    WebhookSmsProvider,
    extract_otp_from_text,
    wait_for_otp,
)


def _msg(recipient="a@x", body="Your code is 123456", subject="OTP",
         received_at=None):
    return InterceptedMessage(
        message_id="m1",
        sender="bot@x",
        recipient=recipient,
        subject=subject,
        body=body,
        received_at=received_at if received_at is not None else time.time(),
    )


class TestExtractOtp(unittest.TestCase):

    def test_default_extracts_6_digits(self):
        self.assertEqual(extract_otp_from_text("Code: 482910 please"), "482910")

    def test_custom_pattern_with_group(self):
        otp = extract_otp_from_text(
            "Your one-time code: ABC-9990",
            pattern=r"ABC-(\d{4})",
        )
        self.assertEqual(otp, "9990")

    def test_no_match_returns_none(self):
        self.assertIsNone(extract_otp_from_text("nothing here"))

    def test_empty_input(self):
        self.assertIsNone(extract_otp_from_text(""))
        self.assertIsNone(extract_otp_from_text(None))  # type: ignore[arg-type]  # NOSONAR S5655 — intentional bad-input test


class TestInMemoryProvider(unittest.TestCase):

    def test_filters_by_recipient(self):
        p = InMemoryProvider()
        p.push(_msg(recipient="alice@x"))
        p.push(_msg(recipient="bob@x"))
        results = p.fetch_messages(recipient="alice@x")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].recipient, "alice@x")

    def test_filters_by_since(self):
        p = InMemoryProvider()
        now = time.time()
        p.push(_msg(received_at=now - 100))
        p.push(_msg(received_at=now + 100))
        results = p.fetch_messages(since=now)
        self.assertEqual(len(results), 1)

    def test_newest_first(self):
        p = InMemoryProvider()
        p.push(_msg(body="old", received_at=10.0))
        p.push(_msg(body="new", received_at=20.0))
        results = p.fetch_messages()
        self.assertEqual(results[0].body, "new")


class TestMailHogProvider(unittest.TestCase):

    def test_parses_v2_payload(self):
        fake_fetch = MagicMock(return_value={
            "items": [
                {
                    "ID": "abc",
                    "Created": "2026-05-24T10:00:00Z",
                    "Content": {
                        "Headers": {
                            "From": ["a@x"], "To": ["b@x"], "Subject": ["Hi"],
                        },
                        "Body": "Code 999111",
                    },
                }
            ]
        })
        provider = MailHogProvider("http://mailhog:8025", http_fetcher=fake_fetch)  # noqa: S5332
        out = provider.fetch_messages(recipient="b@x")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].subject, "Hi")
        self.assertIn("999111", out[0].body)

    def test_non_dict_payload_raises(self):
        provider = MailHogProvider("http://x", http_fetcher=lambda _u: [])  # noqa: S5332
        with self.assertRaises(OtpInterceptError):
            provider.fetch_messages()


class TestMailpitProvider(unittest.TestCase):

    def test_parses_messages_key(self):
        fake_fetch = MagicMock(return_value={
            "messages": [
                {
                    "ID": "id1",
                    "Created": "2026-05-24T10:00:00Z",
                    "From": {"Address": "a@x"},
                    "To": [{"Address": "b@x"}],
                    "Subject": "verify",
                    "Text": "Token 224488",
                }
            ]
        })
        provider = MailpitProvider("http://mailpit", http_fetcher=fake_fetch)  # noqa: S5332
        out = provider.fetch_messages(recipient="b@x")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].sender, "a@x")
        self.assertIn("224488", out[0].body)


class TestWebhookSmsProvider(unittest.TestCase):

    def test_parses_list(self):
        fake_fetch = MagicMock(return_value=[
            {"id": "s1", "from": "+1000", "to": "+1234",
             "body": "Your code 12345", "received_at": "2026-05-24T10:00:00Z"},
        ])
        provider = WebhookSmsProvider("http://sms", http_fetcher=fake_fetch)  # noqa: S5332
        out = provider.fetch_messages(recipient="+1234")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].recipient, "+1234")

    def test_non_list_raises(self):
        provider = WebhookSmsProvider("http://sms", http_fetcher=lambda _u: {})  # noqa: S5332
        with self.assertRaises(OtpInterceptError):
            provider.fetch_messages()


class TestWaitForOtp(unittest.TestCase):

    def test_returns_immediately_if_present(self):
        provider = InMemoryProvider()
        provider.push(_msg(recipient="a@x", body="Code 111222"))
        code = wait_for_otp(provider, "a@x", since=0, timeout=2, poll_interval=0.01)
        self.assertEqual(code, "111222")

    def test_subject_filter(self):
        provider = InMemoryProvider()
        provider.push(_msg(recipient="a@x", subject="Welcome", body="Code 333"))
        provider.push(_msg(recipient="a@x", subject="OTP", body="Code 444444"))
        code = wait_for_otp(
            provider, "a@x",
            since=0, timeout=2, poll_interval=0.01,
            subject_contains="otp",
        )
        self.assertEqual(code, "444444")

    def test_subject_extraction(self):
        provider = InMemoryProvider()
        provider.push(_msg(recipient="a@x", subject="Code 778899 to verify", body=""))
        code = wait_for_otp(provider, "a@x", since=0, timeout=2, poll_interval=0.01)
        self.assertEqual(code, "778899")

    def test_polls_until_arrives(self):
        provider = InMemoryProvider()
        clock = {"now": 0.0}

        def fake_time():
            return clock["now"]

        def fake_sleep(seconds):
            clock["now"] += seconds
            if clock["now"] >= 1.0 and not provider.messages:
                provider.push(_msg(recipient="a@x", body="Code 909090"))

        code = wait_for_otp(
            provider, "a@x",
            since=0, timeout=5, poll_interval=0.5,
            sleep_fn=fake_sleep, time_fn=fake_time,
        )
        self.assertEqual(code, "909090")

    def test_times_out(self):
        provider = InMemoryProvider()
        clock = {"now": 0.0}

        def fake_time():
            return clock["now"]

        def fake_sleep(seconds):
            clock["now"] += seconds

        with self.assertRaises(OtpInterceptError):
            wait_for_otp(
                provider, "a@x",
                since=0, timeout=2, poll_interval=1.0,
                sleep_fn=fake_sleep, time_fn=fake_time,
            )

    def test_skips_messages_before_since(self):
        provider = InMemoryProvider()
        provider.push(_msg(recipient="a@x", body="Code 999000", received_at=10.0))
        with self.assertRaises(OtpInterceptError):
            wait_for_otp(
                provider, "a@x",
                since=20.0, timeout=0.5, poll_interval=0.1,
            )

    def test_bad_provider_raises(self):
        with self.assertRaises(OtpInterceptError):
            wait_for_otp("not a provider", "a@x")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
