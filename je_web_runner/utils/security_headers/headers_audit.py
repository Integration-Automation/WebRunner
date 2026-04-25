"""
HTTP 安全 header 稽核：對給定的 headers 或 URL 檢查常見的硬性建議項目。
HTTP security header audit. Checks the usual suspects (HSTS, CSP, X-Frame-
Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy)
against a headers dict or a freshly fetched URL.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import requests

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class SecurityHeadersError(WebRunnerException):
    """Raised on operational problems (e.g. fetch failure)."""


_DEFAULT_REQUIRED: List[Dict[str, Any]] = [
    {"name": "Strict-Transport-Security", "rule": "presence_and_max_age"},
    {"name": "Content-Security-Policy", "rule": "presence"},
    {"name": "X-Frame-Options", "rule": "deny_or_sameorigin"},
    {"name": "X-Content-Type-Options", "rule": "nosniff"},
    {"name": "Referrer-Policy", "rule": "presence"},
    {"name": "Permissions-Policy", "rule": "presence"},
]


def _lookup_header(headers: Dict[str, str], name: str) -> Optional[str]:
    lower_name = name.lower()
    for header_name, value in headers.items():
        if header_name.lower() == lower_name:
            return value
    return None


def _check_rule(rule: str, value: Optional[str]) -> Optional[str]:
    """Return a problem string when the rule is violated; None if OK."""
    if value is None:
        return "missing"
    lowered = value.lower()
    if rule == "presence":
        return None
    if rule == "presence_and_max_age":
        if "max-age" not in lowered:
            return "no max-age directive"
        return None
    if rule == "deny_or_sameorigin":
        if lowered.strip() not in {"deny", "sameorigin"}:
            return f"unexpected value {value!r}"
        return None
    if rule == "nosniff":
        if lowered.strip() != "nosniff":
            return f"unexpected value {value!r}"
        return None
    return f"unknown rule {rule!r}"


def audit_headers(
    headers: Dict[str, str],
    required: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """
    對 headers dict 套用規則表，回傳所有違反項目
    Apply the rule table against ``headers`` and return findings.

    :param required: 自訂規則表，預設為 ``_DEFAULT_REQUIRED``
    :return: list of {header, rule, problem, value} dicts
    """
    rules = required if required is not None else _DEFAULT_REQUIRED
    findings: List[Dict[str, Any]] = []
    for rule in rules:
        header_name = rule["name"]
        value = _lookup_header(headers, header_name)
        problem = _check_rule(rule["rule"], value)
        if problem is None:
            continue
        findings.append({
            "header": header_name,
            "rule": rule["rule"],
            "problem": problem,
            "value": value,
        })
    return findings


def audit_url(
    url: str,
    timeout: int = 30,
    required: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """
    GET ``url`` 並稽核回應 headers
    Issue a GET request and audit the response headers.
    """
    if not isinstance(url, str) or not (url.startswith("http://") or url.startswith("https://")):
        raise SecurityHeadersError(f"URL must be http(s): {url!r}")
    web_runner_logger.info(f"audit_url: {url}")
    response = requests.get(url, timeout=timeout, allow_redirects=True)
    return audit_headers(dict(response.headers), required=required)
