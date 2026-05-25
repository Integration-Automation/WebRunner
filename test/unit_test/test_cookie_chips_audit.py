"""Unit tests for je_web_runner.utils.cookie_chips_audit."""
import unittest

from je_web_runner.utils.cookie_chips_audit.audit import (
    CookieChipsAuditError,
    Severity,
    assert_no_errors,
    audit_har,
    audit_headers,
    parse_set_cookie,
)


def _set_cookie_entry(url, header_value):
    return {
        "request": {"url": url},
        "response": {"headers": [{"name": "Set-Cookie", "value": header_value}]},
    }


def _har(*entries):
    return {"log": {"entries": list(entries)}}


class TestParse(unittest.TestCase):

    def test_basic(self):
        c = parse_set_cookie("id=42; Path=/; Secure; SameSite=None; Partitioned")
        self.assertEqual(c.name, "id")
        self.assertTrue(c.is_partitioned)
        self.assertTrue(c.is_secure)
        self.assertEqual(c.samesite, "none")

    def test_bad_header(self):
        with self.assertRaises(CookieChipsAuditError):
            parse_set_cookie("nope")

    def test_no_attributes(self):
        c = parse_set_cookie("k=v")
        self.assertEqual(c.attributes, {})


class TestAuditHar(unittest.TestCase):

    def test_third_party_missing_partitioned_is_error(self):
        har = _har(_set_cookie_entry(
            "https://adtech.com/pixel", "id=1; Secure; SameSite=None",
        ))
        findings = audit_har(har, page_url="https://news.example.com/")
        rules = {f.rule for f in findings}
        self.assertIn("third-party-missing-partitioned", rules)

    def test_third_party_with_partitioned_ok(self):
        har = _har(_set_cookie_entry(
            "https://adtech.com/pixel",
            "id=1; Secure; SameSite=None; Partitioned",
        ))
        findings = audit_har(har, page_url="https://news.example.com/")
        # No errors — only optional info
        self.assertEqual(
            [f for f in findings if f.severity == Severity.ERROR], [],
        )

    def test_partitioned_without_secure_errors(self):
        har = _har(_set_cookie_entry(
            "https://adtech.com/p", "id=1; SameSite=None; Partitioned",
        ))
        findings = audit_har(har, page_url="https://news.example.com/")
        rules = {f.rule for f in findings}
        self.assertIn("partitioned-requires-secure", rules)

    def test_partitioned_wrong_samesite_errors(self):
        har = _har(_set_cookie_entry(
            "https://adtech.com/p", "id=1; Secure; SameSite=Lax; Partitioned",
        ))
        findings = audit_har(har, page_url="https://news.example.com/")
        rules = {f.rule for f in findings}
        self.assertIn("partitioned-requires-samesite-none", rules)

    def test_first_party_partitioned_warns(self):
        har = _har(_set_cookie_entry(
            "https://example.com/p",
            "id=1; Secure; SameSite=None; Partitioned",
        ))
        findings = audit_har(har, page_url="https://example.com/")
        rules = {f.rule for f in findings}
        self.assertIn("partitioned-on-first-party", rules)

    def test_first_party_normal_no_findings(self):
        har = _har(_set_cookie_entry(
            "https://example.com/p", "id=1; Secure; SameSite=Lax",
        ))
        findings = audit_har(har, page_url="https://example.com/")
        self.assertEqual(findings, [])

    def test_invalid_har(self):
        with self.assertRaises(CookieChipsAuditError):
            audit_har("nope", "https://x/")

    def test_invalid_page_url(self):
        with self.assertRaises(CookieChipsAuditError):
            audit_har({}, "")

    def test_invalid_entries_type(self):
        with self.assertRaises(CookieChipsAuditError):
            audit_har({"log": {"entries": "x"}}, "https://x/")

    def test_skips_bad_set_cookie(self):
        har = {"log": {"entries": [{
            "request": {"url": "https://x/"},
            "response": {"headers": [{"name": "Set-Cookie", "value": "garbage"}]},
        }]}}
        self.assertEqual(audit_har(har, "https://x/"), [])


class TestAuditHeaders(unittest.TestCase):

    def test_pass_through(self):
        findings = audit_headers(
            ["id=1; Secure; SameSite=None; Partitioned"],
            page_url="https://example.com/",
            cookie_url="https://ads.com/p",
        )
        self.assertEqual(
            [f for f in findings if f.severity == Severity.ERROR], [],
        )

    def test_skip_invalid(self):
        findings = audit_headers(
            ["garbage", "id=1; Secure; SameSite=None; Partitioned"],
            page_url="https://example.com/",
            cookie_url="https://ads.com/p",
        )
        self.assertTrue(all(f.severity != Severity.ERROR for f in findings))


class TestAssertNoErrors(unittest.TestCase):

    def test_pass(self):
        assert_no_errors([])

    def test_fail(self):
        har = _har(_set_cookie_entry(
            "https://adtech.com/p", "id=1; SameSite=None",
        ))
        with self.assertRaises(CookieChipsAuditError):
            assert_no_errors(audit_har(har, "https://news.example.com/"))


if __name__ == "__main__":
    unittest.main()
