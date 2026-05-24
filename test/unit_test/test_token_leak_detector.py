"""Unit tests for je_web_runner.utils.token_leak_detector."""
import base64
import json
import unittest

from je_web_runner.utils.token_leak_detector.detector import (
    DEFAULT_PATTERNS,
    TokenFinding,
    TokenLeakError,
    TokenPattern,
    assert_no_leaks,
    filter_by_severity,
    scan_har,
    scan_log_lines,
    scan_text,
)


def _real_jwt():
    header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').rstrip(b"=").decode()
    body = base64.urlsafe_b64encode(b'{"sub":"x"}').rstrip(b"=").decode()
    sig = base64.urlsafe_b64encode(b"signature_signature").rstrip(b"=").decode()
    return f"{header}.{body}.{sig}"


class TestScanText(unittest.TestCase):

    def test_finds_jwt(self):
        text = f"Authorization: Bearer {_real_jwt()}"
        findings = scan_text(text)
        names = [f.pattern for f in findings]
        self.assertIn("jwt", names)

    def test_skips_fake_jwt(self):
        text = "eyJfake.eyJfake.eyJfake_padding_padding_padding"
        findings = scan_text(text)
        self.assertNotIn("jwt", [f.pattern for f in findings])

    def test_aws_access_key(self):
        text = "AKIAIOSFODNN7EXAMPLE in source"
        findings = scan_text(text)
        self.assertTrue(any(f.pattern == "aws_access_key_id" for f in findings))

    def test_aws_secret_assignment(self):
        text = 'aws_secret_access_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"'
        findings = scan_text(text)
        self.assertTrue(any(f.pattern == "aws_secret_access_key_assignment" for f in findings))

    def test_github_token(self):
        text = f"ghp_{'a' * 36}"
        findings = scan_text(text)
        self.assertTrue(any(f.pattern == "github_token" for f in findings))

    def test_stripe_live(self):
        text = f"sk_live_{'a' * 24}"
        findings = scan_text(text)
        self.assertTrue(any(f.pattern == "stripe_live_secret" for f in findings))

    def test_google_api_key(self):
        text = "AIza" + "B" * 35
        findings = scan_text(text)
        self.assertTrue(any(f.pattern == "google_api_key" for f in findings))

    def test_session_assignment(self):
        text = 'session_id: "abc123def456ghi789jkl"'
        findings = scan_text(text)
        self.assertTrue(any(f.pattern == "session_token_assignment" for f in findings))

    def test_redaction(self):
        text = f"ghp_{'x' * 36}"
        findings = scan_text(text)
        self.assertTrue(findings[0].token_suffix.startswith("…"))

    def test_dedup_within_source(self):
        token = f"ghp_{'a' * 36}"
        text = "\n".join([token] * 5)
        findings = scan_text(text, source="x", location="y")
        # All have the same suffix → dedup to 1
        self.assertEqual(len(findings), 1)

    def test_dedup_differs_by_location(self):
        token = f"ghp_{'a' * 36}"
        findings = scan_text(token, source="x", location="loc1")
        findings += scan_text(token, source="x", location="loc2")
        self.assertEqual(len(findings), 2)

    def test_non_string_rejected(self):
        with self.assertRaises(TokenLeakError):
            scan_text(123)  # type: ignore[arg-type]  # NOSONAR S5655 — intentional bad-input test

    def test_clean_text_returns_empty(self):
        self.assertEqual(scan_text("nothing interesting here"), [])


class TestScanHar(unittest.TestCase):

    def test_scans_response_body(self):
        har = {
            "log": {
                "entries": [
                    {
                        "request": {"url": "https://api/x"},
                        "response": {
                            "content": {"text": f"token={_real_jwt()}"},
                        },
                    }
                ]
            }
        }
        findings = scan_har(har)
        self.assertTrue(any(f.location == "https://api/x" for f in findings))

    def test_scans_request_body(self):
        har = {
            "log": {
                "entries": [
                    {
                        "request": {
                            "url": "https://api/x",
                            "postData": {"text": "AKIAIOSFODNN7EXAMPLE"},
                        },
                        "response": {"content": {}},
                    }
                ]
            }
        }
        findings = scan_har(har)
        self.assertTrue(any(f.source == "har.request" for f in findings))

    def test_string_har(self):
        har = json.dumps({"log": {"entries": []}})
        self.assertEqual(scan_har(har), [])

    def test_bad_har_string(self):
        with self.assertRaises(TokenLeakError):
            scan_har("not json")

    def test_bad_har_type(self):
        with self.assertRaises(TokenLeakError):
            scan_har(123)  # type: ignore[arg-type]

    def test_bad_har_json_shape(self):
        with self.assertRaises(TokenLeakError):
            scan_har(json.dumps([1, 2]))


class TestScanLog(unittest.TestCase):

    def test_scans_lines(self):
        token = f"ghp_{'a' * 36}"
        findings = scan_log_lines(["nothing here", token, "another line"])
        self.assertEqual(len(findings), 1)
        self.assertTrue(findings[0].location.startswith("line:"))

    def test_skips_non_strings(self):
        findings = scan_log_lines([None, 1, "ok"])  # type: ignore[list-item]
        self.assertEqual(findings, [])


class TestAssertions(unittest.TestCase):

    def test_assert_no_leaks_pass(self):
        assert_no_leaks([])

    def test_assert_no_leaks_fail(self):
        with self.assertRaises(TokenLeakError):
            assert_no_leaks([TokenFinding("jwt", "critical", "…abc123", "har")])

    def test_filter_by_severity(self):
        findings = [
            TokenFinding("jwt", "critical", "…1", "x"),
            TokenFinding("session", "medium", "…2", "x"),
            TokenFinding("api", "low", "…3", "x"),
        ]
        self.assertEqual(len(filter_by_severity(findings, minimum="medium")), 2)
        self.assertEqual(len(filter_by_severity(findings, minimum="critical")), 1)

    def test_bad_severity(self):
        with self.assertRaises(TokenLeakError):
            filter_by_severity([], minimum="weird")


class TestCustomPattern(unittest.TestCase):

    def test_custom_pattern(self):
        import re
        custom = TokenPattern(
            name="my_token",
            pattern=re.compile(r"MYAPP-[A-Z0-9]{20}"),
            severity="high",
        )
        findings = scan_text("MYAPP-ABCDEFGHIJKLMNOPQRST", patterns=[custom])
        self.assertEqual(findings[0].pattern, "my_token")

    def test_default_patterns_loaded(self):
        self.assertGreater(len(DEFAULT_PATTERNS), 5)


if __name__ == "__main__":
    unittest.main()
