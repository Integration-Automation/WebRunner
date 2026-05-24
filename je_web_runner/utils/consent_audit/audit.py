"""
GDPR / CCPA 風格 cookie 分類 + 偵測 pre-consent 載入的 non-essential cookies。
Two assertions teams hit most often:

* "No analytics / advertising / social cookies must be set before the
  user clicks 'Accept'."
* "When the user opts out, marketing cookies must not be re-introduced
  by any subsequent page load."

This module compares two cookie snapshots (``before_consent`` and
``after_consent``), classifies each cookie against a built-in catalogue
of well-known vendors, and produces a :class:`ConsentReport`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class ConsentAuditError(WebRunnerException):
    """Raised on malformed cookie inputs or invalid catalogue overrides."""


class CookieCategory(str, Enum):
    """Standard GDPR / IAB categories."""

    NECESSARY = "necessary"
    PREFERENCES = "preferences"
    ANALYTICS = "analytics"
    MARKETING = "marketing"
    SOCIAL = "social"
    UNKNOWN = "unknown"


# ---------- catalogue ---------------------------------------------------

@dataclass(frozen=True)
class CookieRule:
    """Match by cookie name regex and / or domain suffix."""

    name_pattern: Optional[str]
    domain_suffix: Optional[str]
    category: CookieCategory
    vendor: str


_CATALOGUE: Sequence[CookieRule] = (
    CookieRule(r"^_ga(_|$)|^_gid$|^_gat", None, CookieCategory.ANALYTICS, "google_analytics"),
    CookieRule(r"^_fbp$|^_fbc$", None, CookieCategory.MARKETING, "facebook_pixel"),
    CookieRule(r"^_hjSessionUser_|^_hjSession_|^_hjAbsoluteSessionInProgress$",
               None, CookieCategory.ANALYTICS, "hotjar"),
    CookieRule(r"^IDE$", "doubleclick.net", CookieCategory.MARKETING, "google_dv360"),
    CookieRule(r"^MUID$|^MUIDB$", "bing.com", CookieCategory.MARKETING, "microsoft_ads"),
    CookieRule(r"^_pin_unauth$|^_pinterest_", None, CookieCategory.MARKETING, "pinterest"),
    CookieRule(r"^li_gc$|^lidc$|^bcookie$|^bscookie$", "linkedin.com",
               CookieCategory.SOCIAL, "linkedin"),
    CookieRule(r"^datr$|^sb$", "facebook.com", CookieCategory.SOCIAL, "facebook"),
    CookieRule(r"^optimizelyEndUserId$|^optimizely_", None,
               CookieCategory.ANALYTICS, "optimizely"),
    CookieRule(r"^mp_", None, CookieCategory.ANALYTICS, "mixpanel"),
    CookieRule(r"^amplitude_id_", None, CookieCategory.ANALYTICS, "amplitude"),
    CookieRule(r"^XSRF-TOKEN$|^csrftoken$|^__Host-csrf$",
               None, CookieCategory.NECESSARY, "csrf"),
    CookieRule(r"^(session|JSESSIONID|connect\.sid|laravel_session|PHPSESSID)$",
               None, CookieCategory.NECESSARY, "session"),
    CookieRule(r"^locale$|^lang$|^i18n_", None, CookieCategory.PREFERENCES, "i18n"),
    CookieRule(r"^theme$|^darkmode$", None, CookieCategory.PREFERENCES, "ui_preferences"),
)


# ---------- cookie model -----------------------------------------------

@dataclass(frozen=True)
class Cookie:
    """One browser cookie."""

    name: str
    domain: str = ""
    value: Optional[str] = None
    secure: bool = True
    same_site: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.name or not isinstance(self.name, str):
            raise ConsentAuditError("Cookie.name must be a non-empty string")


@dataclass
class ClassifiedCookie:
    """A cookie with its assigned category + vendor."""

    cookie: Cookie
    category: CookieCategory
    vendor: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.cookie.name,
            "domain": self.cookie.domain,
            "category": self.category.value,
            "vendor": self.vendor,
        }


# ---------- classification ---------------------------------------------

def classify_cookie(
    cookie: Cookie,
    *,
    extra_rules: Sequence[CookieRule] = (),
) -> ClassifiedCookie:
    """Run the catalogue + caller-supplied rules against one cookie."""
    if not isinstance(cookie, Cookie):
        raise ConsentAuditError(
            f"classify_cookie expects Cookie, got {type(cookie).__name__}"
        )
    for rule in (*extra_rules, *_CATALOGUE):
        if _matches(rule, cookie):
            return ClassifiedCookie(cookie=cookie, category=rule.category, vendor=rule.vendor)
    return ClassifiedCookie(
        cookie=cookie, category=CookieCategory.UNKNOWN, vendor="unknown",
    )


def _matches(rule: CookieRule, cookie: Cookie) -> bool:
    if rule.name_pattern and not re.search(rule.name_pattern, cookie.name):
        return False
    if rule.domain_suffix and (
        not cookie.domain
        or not cookie.domain.lower().endswith(rule.domain_suffix.lower())
    ):
        return False
    return rule.name_pattern is not None or rule.domain_suffix is not None


def classify_all(
    cookies: Iterable[Cookie],
    *,
    extra_rules: Sequence[CookieRule] = (),
) -> List[ClassifiedCookie]:
    """Convenience: classify every cookie in ``cookies``."""
    return [classify_cookie(c, extra_rules=extra_rules) for c in cookies]


# ---------- audit -------------------------------------------------------

@dataclass
class ConsentReport:
    """Outcome of :func:`audit_consent`."""

    pre_consent_total: int
    post_consent_total: int
    pre_consent_violations: List[ClassifiedCookie] = field(default_factory=list)
    post_consent_reintroduced: List[ClassifiedCookie] = field(default_factory=list)
    unknown_cookies: List[ClassifiedCookie] = field(default_factory=list)

    def passed(self) -> bool:
        return not self.pre_consent_violations and not self.post_consent_reintroduced

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pre_consent_total": self.pre_consent_total,
            "post_consent_total": self.post_consent_total,
            "pre_consent_violations": [c.to_dict() for c in self.pre_consent_violations],
            "post_consent_reintroduced": [c.to_dict() for c in self.post_consent_reintroduced],
            "unknown_cookies": [c.to_dict() for c in self.unknown_cookies],
            "passed": self.passed(),
        }


NON_ESSENTIAL = frozenset({
    CookieCategory.ANALYTICS,
    CookieCategory.MARKETING,
    CookieCategory.SOCIAL,
})


def audit_consent(
    before_consent: Sequence[Cookie],
    after_consent: Sequence[Cookie] = (),
    *,
    user_rejected: bool = False,
    extra_rules: Sequence[CookieRule] = (),
) -> ConsentReport:
    """
    Cross-check that no non-essential cookies are set pre-consent, and
    (when ``user_rejected``) that none re-appear post-rejection.
    """
    before_classified = classify_all(before_consent, extra_rules=extra_rules)
    after_classified = classify_all(after_consent, extra_rules=extra_rules)

    pre_violations = [
        c for c in before_classified if c.category in NON_ESSENTIAL
    ]
    unknown = [
        c for c in before_classified if c.category == CookieCategory.UNKNOWN
    ]
    reintroduced: List[ClassifiedCookie] = []
    if user_rejected:
        reintroduced = [
            c for c in after_classified if c.category in NON_ESSENTIAL
        ]
    return ConsentReport(
        pre_consent_total=len(before_classified),
        post_consent_total=len(after_classified),
        pre_consent_violations=pre_violations,
        post_consent_reintroduced=reintroduced,
        unknown_cookies=unknown,
    )


# ---------- helpers -----------------------------------------------------

def assert_passes(report: ConsentReport) -> None:
    """Raise unless ``report.passed()``."""
    if not isinstance(report, ConsentReport):
        raise ConsentAuditError("assert_passes expects ConsentReport")
    if report.passed():
        return
    parts = []
    if report.pre_consent_violations:
        names = ", ".join(c.cookie.name for c in report.pre_consent_violations)
        parts.append(f"pre-consent non-essential: {names}")
    if report.post_consent_reintroduced:
        names = ", ".join(c.cookie.name for c in report.post_consent_reintroduced)
        parts.append(f"reintroduced after reject: {names}")
    raise ConsentAuditError("; ".join(parts))


def from_selenium_cookies(cookies: Iterable[Dict[str, Any]]) -> List[Cookie]:
    """Convert Selenium ``driver.get_cookies()`` dicts to :class:`Cookie`."""
    out: List[Cookie] = []
    for entry in cookies:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            continue
        out.append(Cookie(
            name=name,
            domain=str(entry.get("domain") or ""),
            value=entry.get("value"),
            secure=bool(entry.get("secure", True)),
            same_site=entry.get("sameSite"),
        ))
    return out
