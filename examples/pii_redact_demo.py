"""
Demo: scan_text + redact_text on a HAR-style log payload, no browser needed.

Useful as a copy-paste for CI gates that want to fail a PR if a captured
HAR / log has PII in it. Add ``allow_categories`` to whitelist legit
matches (e.g. corporate phone in a footer).

Run: python examples/pii_redact_demo.py
"""
from __future__ import annotations

import sys

from je_web_runner.api.security import (
    PiiScannerError,
    assert_no_pii,
    redact_text,
    scan_pii_text,
)


SAMPLE_HAR_BODY = (
    '{"user": {"email": "alice@example.com", "phone": "+15551234567",'
    ' "card": "4111 1111 1111 1111", "ssn": "123-45-6789"},'
    ' "request_ip": "192.168.0.42", "trace_id": "abc-123"}'
)


def main() -> int:
    findings = scan_pii_text(SAMPLE_HAR_BODY)
    print(f"detected {len(findings)} PII match(es):")
    for finding in findings:
        print(f"  - {finding.category:<14} -> {finding.redacted}")

    print("\nredacted preview:")
    print(redact_text(SAMPLE_HAR_BODY))

    print("\nassert_no_pii (allowing ipv4):")
    try:
        assert_no_pii(SAMPLE_HAR_BODY, allow_categories=["ipv4"])
    except PiiScannerError as error:
        # Expected — there are still email / phone / card / SSN matches.
        print(f"  raised as expected: {str(error)[:100]}…")
    return 0


if __name__ == "__main__":
    sys.exit(main())
