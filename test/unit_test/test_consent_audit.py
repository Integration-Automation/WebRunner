"""Unit tests for je_web_runner.utils.consent_audit."""
import unittest

from je_web_runner.utils.consent_audit.audit import (
    ConsentAuditError,
    ConsentReport,
    Cookie,
    CookieCategory,
    CookieRule,
    assert_passes,
    audit_consent,
    classify_all,
    classify_cookie,
    from_selenium_cookies,
)


def _ga():
    return Cookie(name="_ga", domain=".example.com")


def _ga_id():
    return Cookie(name="_ga_ABC123", domain=".example.com")


def _session():
    return Cookie(name="JSESSIONID", domain=".example.com")


def _csrf():
    return Cookie(name="XSRF-TOKEN", domain=".example.com")


def _fbp():
    return Cookie(name="_fbp", domain=".example.com")


class TestCookie(unittest.TestCase):

    def test_rejects_empty_name(self):
        with self.assertRaises(ConsentAuditError):
            Cookie(name="")


class TestClassify(unittest.TestCase):

    def test_ga_is_analytics(self):
        c = classify_cookie(_ga())
        self.assertEqual(c.category, CookieCategory.ANALYTICS)
        self.assertEqual(c.vendor, "google_analytics")

    def test_ga_id_is_analytics(self):
        c = classify_cookie(_ga_id())
        self.assertEqual(c.category, CookieCategory.ANALYTICS)

    def test_fbp_is_marketing(self):
        self.assertEqual(classify_cookie(_fbp()).category, CookieCategory.MARKETING)

    def test_session_is_necessary(self):
        self.assertEqual(classify_cookie(_session()).category, CookieCategory.NECESSARY)

    def test_csrf_is_necessary(self):
        self.assertEqual(classify_cookie(_csrf()).category, CookieCategory.NECESSARY)

    def test_unknown_cookie(self):
        c = classify_cookie(Cookie(name="my_random_cookie"))
        self.assertEqual(c.category, CookieCategory.UNKNOWN)
        self.assertEqual(c.vendor, "unknown")

    def test_extra_rule_wins(self):
        rule = CookieRule(
            name_pattern=r"^my_marketing$",
            domain_suffix=None,
            category=CookieCategory.MARKETING,
            vendor="myco",
        )
        c = classify_cookie(Cookie(name="my_marketing"), extra_rules=[rule])
        self.assertEqual(c.category, CookieCategory.MARKETING)
        self.assertEqual(c.vendor, "myco")

    def test_domain_suffix_required_for_some(self):
        # IDE only counts when on doubleclick.net
        c = classify_cookie(Cookie(name="IDE", domain="example.com"))
        self.assertEqual(c.category, CookieCategory.UNKNOWN)
        c2 = classify_cookie(Cookie(name="IDE", domain="ads.doubleclick.net"))
        self.assertEqual(c2.category, CookieCategory.MARKETING)

    def test_classify_all(self):
        self.assertEqual(len(classify_all([_ga(), _session(), _fbp()])), 3)

    def test_rejects_non_cookie(self):
        with self.assertRaises(ConsentAuditError):
            classify_cookie("string")  # type: ignore[arg-type]


class TestAudit(unittest.TestCase):

    def test_clean_pre_consent(self):
        report = audit_consent(before_consent=[_session(), _csrf()])
        self.assertTrue(report.passed())

    def test_dirty_pre_consent(self):
        report = audit_consent(before_consent=[_session(), _ga(), _fbp()])
        self.assertFalse(report.passed())
        self.assertEqual(len(report.pre_consent_violations), 2)

    def test_reintroduced_after_reject(self):
        report = audit_consent(
            before_consent=[_session()],
            after_consent=[_session(), _ga()],
            user_rejected=True,
        )
        self.assertFalse(report.passed())
        self.assertEqual(len(report.post_consent_reintroduced), 1)

    def test_reintroduced_ignored_when_not_rejected(self):
        report = audit_consent(
            before_consent=[_session()],
            after_consent=[_session(), _ga()],
            user_rejected=False,
        )
        self.assertTrue(report.passed())

    def test_unknown_collected(self):
        c = Cookie(name="weird_cookie", domain="x.com")
        report = audit_consent(before_consent=[c])
        self.assertEqual(len(report.unknown_cookies), 1)

    def test_report_to_dict(self):
        report = audit_consent(before_consent=[_ga()])
        data = report.to_dict()
        self.assertFalse(data["passed"])
        self.assertEqual(len(data["pre_consent_violations"]), 1)


class TestAssertPasses(unittest.TestCase):

    def test_pass(self):
        assert_passes(ConsentReport(pre_consent_total=0, post_consent_total=0))

    def test_fail_pre_consent(self):
        report = audit_consent(before_consent=[_ga()])
        with self.assertRaises(ConsentAuditError):
            assert_passes(report)

    def test_fail_reintroduced(self):
        report = audit_consent(
            before_consent=[], after_consent=[_ga()], user_rejected=True,
        )
        with self.assertRaises(ConsentAuditError):
            assert_passes(report)

    def test_rejects_non_report(self):
        with self.assertRaises(ConsentAuditError):
            assert_passes("not a report")  # type: ignore[arg-type]


class TestFromSelenium(unittest.TestCase):

    def test_converts(self):
        raw = [
            {"name": "_ga", "domain": ".x.com", "value": "1", "secure": True},
            {"name": "JSESSIONID", "domain": ".x.com", "secure": False, "sameSite": "Lax"},
        ]
        cookies = from_selenium_cookies(raw)
        self.assertEqual(len(cookies), 2)
        self.assertEqual(cookies[0].name, "_ga")
        self.assertEqual(cookies[1].same_site, "Lax")

    def test_skips_nameless(self):
        cookies = from_selenium_cookies([{"value": "x"}, "not dict"])  # type: ignore[list-item]
        self.assertEqual(cookies, [])


if __name__ == "__main__":
    unittest.main()
