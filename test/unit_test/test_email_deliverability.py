"""Unit tests for je_web_runner.utils.email_deliverability."""
import unittest

from je_web_runner.utils.email_deliverability.headers import (
    EmailDeliverabilityError,
    assert_dkim_pass,
    assert_dmarc_pass,
    assert_list_unsubscribe,
    assert_no_bcc_leak,
    assert_spf_pass,
    parse_headers,
)


GOOD = """\
From: noreply@example.com
To: user@example.org
Subject: Welcome
DKIM-Signature: v=1; a=rsa-sha256; d=example.com; s=mail; t=1700000000;
\tbh=abc; b=def
Received-SPF: pass (mx.example.org: domain of example.com designates ...)
Authentication-Results: mx.example.org;
\tspf=pass smtp.mailfrom=example.com;
\tdkim=pass header.d=example.com;
\tdmarc=pass policy.dmarc=reject
List-Unsubscribe: <https://example.com/unsub?u=1>
List-Unsubscribe-Post: List-Unsubscribe=One-Click

body
"""


class TestParse(unittest.TestCase):

    def test_basic(self):
        hm = parse_headers(GOOD)
        self.assertEqual(hm.get_first("From"), "noreply@example.com")

    def test_continuation_joined(self):
        hm = parse_headers(GOOD)
        sig = hm.get_first("DKIM-Signature")
        self.assertIn("bh=abc", sig)

    def test_bad_type(self):
        with self.assertRaises(EmailDeliverabilityError):
            parse_headers(123)  # NOSONAR python:S5655 - deliberate bad input


class TestSpf(unittest.TestCase):

    def test_pass(self):
        assert_spf_pass(parse_headers(GOOD))

    def test_fail(self):
        with self.assertRaises(EmailDeliverabilityError):
            assert_spf_pass(parse_headers("Subject: x\n\nbody"))


class TestDkim(unittest.TestCase):

    def test_pass(self):
        assert_dkim_pass(parse_headers(GOOD))

    def test_no_signature(self):
        with self.assertRaises(EmailDeliverabilityError):
            assert_dkim_pass(parse_headers("Subject: x\n\nbody"))

    def test_signature_no_pass(self):
        raw = ("DKIM-Signature: v=1; d=x; b=y\n"
               "Authentication-Results: x; dkim=neutral\n\nbody")
        with self.assertRaises(EmailDeliverabilityError):
            assert_dkim_pass(parse_headers(raw))


class TestDmarc(unittest.TestCase):

    def test_pass(self):
        assert_dmarc_pass(parse_headers(GOOD), expected_policy="reject")

    def test_no_pass(self):
        with self.assertRaises(EmailDeliverabilityError):
            assert_dmarc_pass(parse_headers("Subject: x\n\nbody"))

    def test_wrong_policy(self):
        with self.assertRaises(EmailDeliverabilityError):
            assert_dmarc_pass(parse_headers(GOOD), expected_policy="none")


class TestListUnsubscribe(unittest.TestCase):

    def test_pass(self):
        assert_list_unsubscribe(parse_headers(GOOD))

    def test_missing(self):
        with self.assertRaises(EmailDeliverabilityError):
            assert_list_unsubscribe(parse_headers("Subject: x\n\nbody"))

    def test_missing_post(self):
        raw = "List-Unsubscribe: <https://x/u>\n\nbody"
        with self.assertRaises(EmailDeliverabilityError):
            assert_list_unsubscribe(parse_headers(raw))


class TestBccLeak(unittest.TestCase):

    def test_pass(self):
        assert_no_bcc_leak(parse_headers(GOOD))

    def test_fail(self):
        with self.assertRaises(EmailDeliverabilityError):
            assert_no_bcc_leak(parse_headers("Bcc: leak@x\n\nbody"))


if __name__ == "__main__":
    unittest.main()
