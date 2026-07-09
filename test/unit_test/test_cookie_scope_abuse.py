"""Unit tests for je_web_runner.utils.cookie_scope_abuse."""
import unittest

from je_web_runner.utils.cookie_scope_abuse.scope import (
    CookieScopeAbuseError,
    CookieScopeFinding,
    Severity,
    assert_no_errors,
    audit_cookie,
    audit_many,
)


def _c(**kw):
    base = {"name": "sid", "value": "abcdef1234567890abcdef",
            "domain": "app.example.com", "path": "/api",
            "httpOnly": True, "secure": True, "sameSite": "Lax"}
    base.update(kw)
    return base


class TestAuditOne(unittest.TestCase):

    def test_clean(self):
        findings = audit_cookie(_c(), page_host="app.example.com")
        self.assertEqual(findings, [])

    def test_apex_scoped(self):
        findings = audit_cookie(_c(domain=".example.com"),
                                page_host="app.example.com")
        rules = {f.rule for f in findings}
        self.assertIn("session-on-apex", rules)

    def test_root_path(self):
        findings = audit_cookie(_c(path="/"), page_host="app.example.com")
        rules = {f.rule for f in findings}
        self.assertIn("session-path-root", rules)

    def test_no_httponly(self):
        findings = audit_cookie(_c(httpOnly=False), page_host="app.example.com")
        rules = {f.rule for f in findings}
        self.assertIn("session-no-httponly", rules)

    def test_no_httponly_honours_explicit_false(self):
        # An explicit httpOnly=False must not be masked by a stray snake_case
        # http_only=True (the audit flags *missing* HttpOnly).
        findings = audit_cookie(
            _c(httpOnly=False, http_only=True), page_host="app.example.com"
        )
        self.assertIn("session-no-httponly", {f.rule for f in findings})

    def test_no_secure(self):
        findings = audit_cookie(_c(secure=False), page_host="app.example.com")
        self.assertIn("session-no-secure", {f.rule for f in findings})

    def test_bad_samesite(self):
        findings = audit_cookie(_c(sameSite="None"), page_host="app.example.com")
        self.assertIn("session-bad-samesite", {f.rule for f in findings})

    def test_non_session_passes(self):
        findings = audit_cookie(
            {"name": "lang", "value": "en", "path": "/"},
            page_host="example.com",
        )
        self.assertEqual(findings, [])

    def test_bad_cookie(self):
        with self.assertRaises(CookieScopeAbuseError):
            audit_cookie("nope", page_host="x")

    def test_bad_host(self):
        with self.assertRaises(CookieScopeAbuseError):
            audit_cookie({}, page_host="")


class TestAuditMany(unittest.TestCase):

    def test_aggregates(self):
        findings = audit_many(
            [_c(httpOnly=False), _c(secure=False)],
            page_host="app.example.com",
        )
        self.assertEqual(len(findings), 2)


class TestAssert(unittest.TestCase):

    def test_pass(self):
        assert_no_errors([CookieScopeFinding(
            severity=Severity.WARN, rule="x", cookie="y", message="",
        )])

    def test_fail(self):
        with self.assertRaises(CookieScopeAbuseError):
            assert_no_errors([CookieScopeFinding(
                severity=Severity.ERROR, rule="x", cookie="y", message="",
            )])


if __name__ == "__main__":
    unittest.main()
