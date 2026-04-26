"""Façade: PII / license / CSP / cookie consent / header tampering."""
from je_web_runner.utils.cookie_consent.consent import (
    ConsentBannerError,
    ConsentDismisser,
    common_dismiss_selectors,
    register_selector,
)
from je_web_runner.utils.csp_reporter.reporter import (
    CspReporterError,
    CspViolation,
    CspViolationCollector,
    assert_no_violations,
    collect_violations,
    install_listener,
)
from je_web_runner.utils.header_tampering.tamper import (
    HeaderRule,
    HeaderTampering,
    HeaderTamperingError,
    apply_to_request_headers,
)
from je_web_runner.utils.license_scanner.scanner import (
    LicenseFinding,
    LicenseScannerError,
    assert_allowed_licenses,
    scan_text as scan_license_text,
)
from je_web_runner.utils.pii_scanner.scanner import (
    PiiFinding,
    PiiScannerError,
    assert_no_pii,
    redact_text,
    scan_text as scan_pii_text,
)

__all__ = [
    "ConsentBannerError", "ConsentDismisser",
    "common_dismiss_selectors", "register_selector",
    "CspReporterError", "CspViolation", "CspViolationCollector",
    "assert_no_violations", "collect_violations", "install_listener",
    "HeaderRule", "HeaderTampering", "HeaderTamperingError",
    "apply_to_request_headers",
    "LicenseFinding", "LicenseScannerError",
    "assert_allowed_licenses", "scan_license_text",
    "PiiFinding", "PiiScannerError",
    "assert_no_pii", "redact_text", "scan_pii_text",
]
