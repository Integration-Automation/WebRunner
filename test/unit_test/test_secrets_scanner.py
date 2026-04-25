import json
import os
import tempfile
import unittest
from pathlib import Path

from je_web_runner.utils.secrets_scanner.scanner import (
    SecretsFound,
    assert_no_secrets,
    scan_action,
    scan_action_file,
)


class TestPatternDetection(unittest.TestCase):

    def test_aws_access_key_detected(self):
        findings = scan_action({"key": "AKIAABCDEFGHIJKLMNOP"})
        self.assertTrue(any(f["rule"] == "aws_access_key" for f in findings))

    def test_github_token_detected(self):
        findings = scan_action(["ghp_" + "a" * 36])
        self.assertTrue(any(f["rule"] == "github_token" for f in findings))

    def test_jwt_detected(self):
        jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTYifQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV"
        findings = scan_action(jwt)
        self.assertTrue(any(f["rule"] == "jwt" for f in findings))

    def test_slack_webhook_detected(self):
        findings = scan_action({"hook": "https://hooks.slack.com/services/T00/B00/XXXXXX"})
        self.assertTrue(any(f["rule"] == "slack_webhook" for f in findings))

    def test_private_key_block_detected(self):
        findings = scan_action({"k": "-----BEGIN RSA PRIVATE KEY-----\nfoo\n"})
        self.assertTrue(any(f["rule"] == "private_key" for f in findings))


# Fixtures below intentionally contain credential-shaped strings so the
# scanner can prove it flags them. SonarCloud S2068 / S6418 are false
# positives on these test inputs.
class TestSuspiciousKeyHeuristic(unittest.TestCase):

    def test_high_entropy_value_under_password_key(self):
        action = [["WR_input", {"password": "Ab12cd34Ef56gh78Ij90KlMnOp"}]]  # nosec B105
        findings = scan_action(action)
        self.assertTrue(
            any(f["rule"] == "suspicious_key_high_entropy" for f in findings)
        )

    def test_env_placeholder_not_flagged(self):
        action = [["WR_input", {"password": "${ENV.PASSWORD}"}]]  # nosec B105
        findings = scan_action(action)
        self.assertEqual(findings, [])

    def test_short_value_under_password_key_not_flagged(self):
        action = [["WR_input", {"password": "abc"}]]  # nosec B105
        findings = scan_action(action)
        self.assertEqual(findings, [])


class TestActionFile(unittest.TestCase):

    def test_file_round_trip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "actions.json")
            # Fake key value used to verify the scanner's pattern hits.
            Path(path).write_text(  # nosec B105
                json.dumps([["x", {"api_key": "AKIAABCDEFGHIJKLMNOP"}]]),
                encoding="utf-8",
            )
            findings = scan_action_file(path)
            self.assertGreater(len(findings), 0)


class TestAssertNoSecrets(unittest.TestCase):

    def test_assert_passes_when_clean(self):
        assert_no_secrets([["WR_to_url", {"url": "https://example.com"}]])

    def test_assert_raises_on_finding(self):
        with self.assertRaises(SecretsFound):
            assert_no_secrets({"k": "AKIAABCDEFGHIJKLMNOP"})


if __name__ == "__main__":
    unittest.main()
