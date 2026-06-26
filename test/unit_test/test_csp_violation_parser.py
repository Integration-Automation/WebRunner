"""Unit tests for je_web_runner.utils.csp_violation_parser."""
import unittest

from je_web_runner.utils.csp_violation_parser.parser import (
    CspViolationParserError,
    Violation,
    assert_no_enforced_violations,
    group_by_directive,
    looks_like_recon,
    parse_many,
    parse_one,
    top_blocked_hosts,
)


LEGACY = {
    "csp-report": {
        "document-uri": "https://example.com/",
        "violated-directive": "script-src 'self'",
        "blocked-uri": "https://evil.com/x.js",
        "disposition": "enforce",
    },
}

V3 = {
    "documentURL": "https://example.com/",
    "effectiveDirective": "img-src",
    "blockedURL": "https://cdn.example.net/x.png",
    "disposition": "report",
}


class TestParseOne(unittest.TestCase):

    def test_legacy(self):
        v = parse_one(LEGACY)
        self.assertEqual(v.blocked_uri, "https://evil.com/x.js")

    def test_v3(self):
        v = parse_one(V3)
        self.assertEqual(v.violated_directive, "img-src")
        self.assertEqual(v.disposition, "report")

    def test_bad(self):
        with self.assertRaises(CspViolationParserError):
            parse_one("nope")

    def test_bad_inner(self):
        with self.assertRaises(CspViolationParserError):
            parse_one({"csp-report": "nope"})

    def test_line_number_parsed(self):
        v = parse_one({"line-number": 42})
        self.assertEqual(v.line_number, 42)

    def test_line_number_zero_is_kept(self):
        # 0 is a valid line number and must not fall through to lineNumber.
        v = parse_one({"line-number": 0, "lineNumber": 99})
        self.assertEqual(v.line_number, 0)

    def test_line_number_camelcase_fallback(self):
        v = parse_one({"lineNumber": 7})
        self.assertEqual(v.line_number, 7)

    def test_line_number_missing_defaults_zero(self):
        self.assertEqual(parse_one({}).line_number, 0)

    def test_line_number_non_numeric_defaults_zero(self):
        # Malformed input must not crash the parser.
        self.assertEqual(parse_one({"line-number": "abc"}).line_number, 0)


class TestParseMany(unittest.TestCase):

    def test_basic(self):
        out = parse_many([LEGACY, V3])
        self.assertEqual(len(out), 2)


class TestGroup(unittest.TestCase):

    def test_basic(self):
        groups = group_by_directive([parse_one(LEGACY), parse_one(V3)])
        self.assertIn("script-src 'self'", groups)
        self.assertIn("img-src", groups)


class TestTopHosts(unittest.TestCase):

    def test_count(self):
        violations = [
            Violation(blocked_uri="https://a.com/x"),
            Violation(blocked_uri="https://a.com/y"),
            Violation(blocked_uri="https://b.com/z"),
        ]
        out = top_blocked_hosts(violations, top_n=2)
        self.assertEqual(out[0]["host"], "a.com")
        self.assertEqual(out[0]["count"], 2)

    def test_bad_n(self):
        with self.assertRaises(CspViolationParserError):
            top_blocked_hosts([], top_n=0)


class TestNoEnforced(unittest.TestCase):

    def test_pass(self):
        assert_no_enforced_violations([
            Violation(violated_directive="img-src", disposition="report"),
        ])

    def test_fail(self):
        with self.assertRaises(CspViolationParserError):
            assert_no_enforced_violations([parse_one(LEGACY)])


class TestRecon(unittest.TestCase):

    def test_detected(self):
        violations = [
            Violation(violated_directive="script-src",
                      blocked_uri=f"https://h{i}.com/x") for i in range(6)
        ]
        flagged = looks_like_recon(violations, distinct_hosts_threshold=5)
        self.assertIn("script-src", flagged)

    def test_clean(self):
        self.assertEqual(looks_like_recon([], distinct_hosts_threshold=5), [])

    def test_bad_threshold(self):
        with self.assertRaises(CspViolationParserError):
            looks_like_recon([], distinct_hosts_threshold=1)


if __name__ == "__main__":
    unittest.main()
