"""Facade: Security and privacy audits: headers, cookies, CORS, XSS, redirects, TLS, secrets, PII, SBOM."""
from je_web_runner.utils.clickjacking_audit.audit import (
    ClickjackingAuditError, Verdict as ClickjackingAuditVerdict, HeaderPolicy, parse_response_headers,
    classify as clickjacking_audit_classify, build_probe_page, AuditReport, audit, assert_protected,
)
from je_web_runner.utils.consent_audit.audit import (
    ConsentAuditError, CookieCategory, CookieRule, Cookie, ClassifiedCookie, classify_cookie, classify_all,
    ConsentReport, audit_consent, assert_passes, from_selenium_cookies,
)
from je_web_runner.utils.cookie_chips_audit.audit import (
    CookieChipsAuditError, Severity as CookieChipsAuditSeverity, SetCookie, parse_set_cookie, Finding, audit_har,
    audit_headers as cookie_chips_audit_audit_headers, assert_no_errors as cookie_chips_audit_assert_no_errors,
)
from je_web_runner.utils.cookie_scope_abuse.scope import (
    CookieScopeAbuseError, Severity as CookieScopeAbuseSeverity, CookieScopeFinding, audit_cookie, audit_many,
    assert_no_errors as cookie_scope_abuse_assert_no_errors,
)
from je_web_runner.utils.coop_coep_audit.audit import (
    CoopCoepAuditError, CoopValue, CoepValue, CorpValue, PagePolicy, parse_page_headers, ResourceFinding,
    scan_har_resources, IsolationReport, audit_isolation, assert_isolated,
)
from je_web_runner.utils.cors_matrix.matrix import (
    CorsMatrixError, CorsOutcome, CorsCase, build_matrix, CorsResponse, CorsResult,
    classify as cors_matrix_classify, run_matrix, assert_origin_blocked,
    assert_credentials_require_explicit_origin,
)
from je_web_runner.utils.csp_violation_parser.parser import (
    CspViolationParserError, Violation, parse_one, parse_many, group_by_directive, top_blocked_hosts,
    assert_no_enforced_violations, looks_like_recon,
)
from je_web_runner.utils.dom_xss_taint.taint import (
    DomXssTaintError, TaintFinding, make_canaries, parse_findings, assert_no_taint, assert_only_safe_sinks,
)
from je_web_runner.utils.hsts_preload_audit.audit import (
    HstsPreloadAuditError, HstsHeader, parse_header, assert_preload_ready, assert_served_over_https,
)
from je_web_runner.utils.mixed_content_audit.audit import (
    MixedContentAuditError, Severity as MixedContentAuditSeverity, MixedFinding,
    scan_har as mixed_content_audit_scan_har, scan_console_errors, assert_no_active,
    assert_clean as mixed_content_audit_assert_clean, summary,
)
from je_web_runner.utils.oauth_pkce_replay.replay import (
    OauthPkceReplayError, ReplayOutcome, generate_verifier, challenge_for, TokenExchangeResponse, ReplayCase,
    ReplayResult, replay, run_cases, assert_all_rejected,
)
from je_web_runner.utils.open_redirect_detector.detector import (
    OpenRedirectError, ProbeOutcome, RedirectPayload, default_payloads, ProbeResult, classify_response,
    ProbeResponse, ProbeReport, probe_all, assert_safe,
)
from je_web_runner.utils.pii_in_screenshot.scanner import (
    PiiInScreenshotError, PiiRule, PiiFinding, scan_image, scan_text_only, ScanReport, scan_screenshots,
    assert_clean as pii_in_screenshot_assert_clean,
)
from je_web_runner.utils.sbom_diff.diff import (
    SbomDiffError, Component, VersionChange, SbomReport, diff_sboms, assert_no_new_vulnerable,
    assert_no_disallowed_licenses, report_markdown,
)
from je_web_runner.utils.secrets_scanner.scanner import (
    SecretsFound, scan_action, scan_action_file, assert_no_secrets,
)
from je_web_runner.utils.security_headers.headers_audit import (
    SecurityHeadersError, audit_headers as security_headers_audit_headers, audit_url,
)
from je_web_runner.utils.sri_verify.verify import (
    SriVerifyError, Verdict as SriVerifyVerdict, ResourceTag, parse_html, compute_integrity, SriFinding,
    verify_tag, verify_html, assert_all_ok,
)
from je_web_runner.utils.tls_cipher_audit.audit import (
    TlsCipherAuditError, TlsHandshakeReport, handshake, assert_modern_tls, assert_cipher_safe,
    assert_subject_matches,
)
from je_web_runner.utils.token_leak_detector.detector import (
    TokenLeakError, TokenPattern, TokenFinding, scan_text, scan_har as token_leak_detector_scan_har,
    scan_log_lines, assert_no_leaks, filter_by_severity,
)
from je_web_runner.utils.webhook_signature_verify.verify import (
    WebhookSignatureVerifyError, Scheme, VerifyResult, verify, assert_valid, sign_github, sign_stripe, sign_slack,
)

__all__ = [
    "ClickjackingAuditError", "ClickjackingAuditVerdict", "HeaderPolicy", "parse_response_headers",
    "clickjacking_audit_classify", "build_probe_page", "AuditReport", "audit", "assert_protected",
    "ConsentAuditError", "CookieCategory", "CookieRule", "Cookie", "ClassifiedCookie", "classify_cookie",
    "classify_all", "ConsentReport", "audit_consent", "assert_passes", "from_selenium_cookies",
    "CookieChipsAuditError", "CookieChipsAuditSeverity", "SetCookie", "parse_set_cookie", "Finding", "audit_har",
    "cookie_chips_audit_audit_headers", "cookie_chips_audit_assert_no_errors", "CookieScopeAbuseError",
    "CookieScopeAbuseSeverity", "CookieScopeFinding", "audit_cookie", "audit_many",
    "cookie_scope_abuse_assert_no_errors", "CoopCoepAuditError", "CoopValue", "CoepValue", "CorpValue",
    "PagePolicy", "parse_page_headers", "ResourceFinding", "scan_har_resources", "IsolationReport",
    "audit_isolation", "assert_isolated", "CorsMatrixError", "CorsOutcome", "CorsCase", "build_matrix",
    "CorsResponse", "CorsResult", "cors_matrix_classify", "run_matrix", "assert_origin_blocked",
    "assert_credentials_require_explicit_origin", "CspViolationParserError", "Violation", "parse_one",
    "parse_many", "group_by_directive", "top_blocked_hosts", "assert_no_enforced_violations", "looks_like_recon",
    "DomXssTaintError", "TaintFinding", "make_canaries", "parse_findings", "assert_no_taint",
    "assert_only_safe_sinks", "HstsPreloadAuditError", "HstsHeader", "parse_header", "assert_preload_ready",
    "assert_served_over_https", "MixedContentAuditError", "MixedContentAuditSeverity", "MixedFinding",
    "mixed_content_audit_scan_har", "scan_console_errors", "assert_no_active", "mixed_content_audit_assert_clean",
    "summary", "OauthPkceReplayError", "ReplayOutcome", "generate_verifier", "challenge_for",
    "TokenExchangeResponse", "ReplayCase", "ReplayResult", "replay", "run_cases", "assert_all_rejected",
    "OpenRedirectError", "ProbeOutcome", "RedirectPayload", "default_payloads", "ProbeResult", "classify_response",
    "ProbeResponse", "ProbeReport", "probe_all", "assert_safe", "PiiInScreenshotError", "PiiRule", "PiiFinding",
    "scan_image", "scan_text_only", "ScanReport", "scan_screenshots", "pii_in_screenshot_assert_clean",
    "SbomDiffError", "Component", "VersionChange", "SbomReport", "diff_sboms", "assert_no_new_vulnerable",
    "assert_no_disallowed_licenses", "report_markdown", "SecretsFound", "scan_action", "scan_action_file",
    "assert_no_secrets", "SecurityHeadersError", "security_headers_audit_headers", "audit_url", "SriVerifyError",
    "SriVerifyVerdict", "ResourceTag", "parse_html", "compute_integrity", "SriFinding", "verify_tag",
    "verify_html", "assert_all_ok", "TlsCipherAuditError", "TlsHandshakeReport", "handshake", "assert_modern_tls",
    "assert_cipher_safe", "assert_subject_matches", "TokenLeakError", "TokenPattern", "TokenFinding", "scan_text",
    "token_leak_detector_scan_har", "scan_log_lines", "assert_no_leaks", "filter_by_severity",
    "WebhookSignatureVerifyError", "Scheme", "VerifyResult", "verify", "assert_valid", "sign_github",
    "sign_stripe", "sign_slack",
]
