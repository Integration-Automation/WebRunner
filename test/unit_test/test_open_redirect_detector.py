"""Unit tests for je_web_runner.utils.open_redirect_detector."""
import unittest

from je_web_runner.utils.open_redirect_detector.detector import (
    OpenRedirectError,
    ProbeOutcome,
    ProbeReport,
    ProbeResponse,
    ProbeResult,
    RedirectPayload,
    assert_safe,
    classify_response,
    default_payloads,
    probe_all,
)


class TestPayloads(unittest.TestCase):

    def test_default_set_includes_classics(self):
        names = {p.label for p in default_payloads("evil.example")}
        for needed in ("absolute_http", "scheme_relative", "javascript_uri",
                       "data_uri", "at_sign_userinfo"):
            self.assertIn(needed, names)

    def test_attacker_host_required(self):
        with self.assertRaises(OpenRedirectError):
            default_payloads("no_dot")


class TestClassify(unittest.TestCase):

    def _p(self, value):
        return RedirectPayload(label="x", value=value)

    def test_off_origin_absolute_allowed(self):
        r = classify_response(
            self._p("https://evil.example/"),
            "https://evil.example/", 302,
            legitimate_host="trusted.com",
        )
        self.assertEqual(r.outcome, ProbeOutcome.ALLOWED)

    def test_same_origin_blocked(self):
        r = classify_response(
            self._p("/home"), "https://trusted.com/home", 302,
            legitimate_host="trusted.com",
        )
        self.assertEqual(r.outcome, ProbeOutcome.BLOCKED)

    def test_subdomain_same_org(self):
        r = classify_response(
            self._p("//sub.trusted.com/"),
            "https://sub.trusted.com/", 302,
            legitimate_host="trusted.com",
        )
        self.assertEqual(r.outcome, ProbeOutcome.BLOCKED)

    def test_scheme_relative_evil(self):
        r = classify_response(
            self._p("//evil.example/"),
            "//evil.example/", 302,
            legitimate_host="trusted.com",
        )
        self.assertEqual(r.outcome, ProbeOutcome.ALLOWED)

    def test_javascript_uri(self):
        r = classify_response(
            self._p("javascript:alert(1)"),
            "javascript:alert(1)", 302,
            legitimate_host="trusted.com",
        )
        self.assertEqual(r.outcome, ProbeOutcome.ALLOWED)

    def test_data_uri(self):
        r = classify_response(
            self._p("data:text/html,x"),
            "data:text/html,x", 302,
            legitimate_host="trusted.com",
        )
        self.assertEqual(r.outcome, ProbeOutcome.ALLOWED)

    def test_non_redirect_status_blocked(self):
        r = classify_response(
            self._p("x"), "https://evil.example/", 200,
            legitimate_host="trusted.com",
        )
        self.assertEqual(r.outcome, ProbeOutcome.BLOCKED)

    def test_empty_location_ambiguous(self):
        r = classify_response(
            self._p("x"), None, 302,
            legitimate_host="trusted.com",
        )
        self.assertEqual(r.outcome, ProbeOutcome.AMBIGUOUS)

    def test_at_sign_resolves_evil(self):
        r = classify_response(
            self._p("https://trusted.com@evil.example/"),
            "https://trusted.com@evil.example/", 302,
            legitimate_host="trusted.com",
        )
        # Hostname after @ is evil.example
        self.assertEqual(r.outcome, ProbeOutcome.ALLOWED)

    def test_bad_status_type(self):
        with self.assertRaises(OpenRedirectError):
            classify_response(self._p("x"), None, "302",  # type: ignore[arg-type]  # NOSONAR S5655 — intentional bad-input test
                              legitimate_host="x.com")

    def test_bad_host(self):
        with self.assertRaises(OpenRedirectError):
            classify_response(self._p("x"), None, 302, legitimate_host="")


class TestProbeAll(unittest.TestCase):

    def test_runs_all_payloads(self):
        def probe(value):
            # Naive vulnerable app: always 302s to the input
            return ProbeResponse(status_code=302, location=value)
        report = probe_all(
            default_payloads("evil.example"),
            probe,
            legitimate_host="trusted.com",
        )
        self.assertEqual(len(report.results), len(default_payloads("evil.example")))
        self.assertFalse(report.passed())

    def test_safe_app(self):
        def probe(_value):
            return ProbeResponse(status_code=302, location="https://trusted.com/")
        report = probe_all(
            default_payloads("evil.example"),
            probe, legitimate_host="trusted.com",
        )
        self.assertTrue(report.passed())

    def test_empty_payloads(self):
        with self.assertRaises(OpenRedirectError):
            probe_all([], lambda _v: ProbeResponse(200, None), legitimate_host="x.com")

    def test_non_callable_probe(self):
        with self.assertRaises(OpenRedirectError):
            probe_all([RedirectPayload("x", "y")], "not callable",  # type: ignore[arg-type]
                      legitimate_host="x.com")

    def test_probe_exception_wrapped(self):
        def boom(_):
            raise RuntimeError("net")
        with self.assertRaises(OpenRedirectError):
            probe_all([RedirectPayload("x", "y")], boom, legitimate_host="x.com")

    def test_bad_probe_return(self):
        def bad(_):
            return "not a probe response"
        with self.assertRaises(OpenRedirectError):
            probe_all([RedirectPayload("x", "y")], bad, legitimate_host="x.com")


class TestAssertSafe(unittest.TestCase):

    def test_pass(self):
        assert_safe(ProbeReport(legitimate_host="x"))

    def test_fail(self):
        report = ProbeReport(legitimate_host="x", results=[
            ProbeResult(
                payload=RedirectPayload("evil", "//evil/"),
                final_location="//evil/", status_code=302,
                outcome=ProbeOutcome.ALLOWED,
            ),
        ])
        with self.assertRaises(OpenRedirectError):
            assert_safe(report)

    def test_rejects_non_report(self):
        with self.assertRaises(OpenRedirectError):
            assert_safe("nope")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
