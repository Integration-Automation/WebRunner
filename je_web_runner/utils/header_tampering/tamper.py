"""
Per-request header 篡改：改 cookie / referer / origin / authorization 看反應。
Header tampering for security testing. Adds, removes, or replaces specific
HTTP headers on outgoing requests so testers can probe missing CSRF tokens,
mismatched origins, or stripped auth.

Drives Playwright's ``page.route()`` API; the rule list is also usable via
``apply_to_request_headers`` for plain-Python HTTP testing.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Pattern

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class HeaderTamperingError(WebRunnerException):
    """Raised when a rule is malformed or driver does not expose route()."""


@dataclass
class HeaderRule:
    """One ``(url_match, header, action)`` directive."""

    name: str  # diagnostic label
    header: str
    action: str  # "set" | "remove" | "append"
    value: Optional[str] = None
    url_match: Optional[Pattern] = None

    def __post_init__(self) -> None:
        if not self.header:
            raise HeaderTamperingError("header name required")
        if self.action not in {"set", "remove", "append"}:
            raise HeaderTamperingError(
                f"action must be set/remove/append, got {self.action!r}"
            )
        if self.action != "remove" and self.value is None:
            raise HeaderTamperingError(
                f"action {self.action!r} requires a value"
            )


def _matches(rule: HeaderRule, url: str) -> bool:
    if rule.url_match is None:
        return True
    return bool(rule.url_match.search(url))


def apply_to_request_headers(
    headers: Dict[str, str],
    url: str,
    rules: List[HeaderRule],
) -> Dict[str, str]:
    """Return a new headers dict with all matching rules applied."""
    next_headers = {k: v for k, v in headers.items()}
    for rule in rules:
        if not _matches(rule, url):
            continue
        if rule.action == "set":
            next_headers[rule.header] = rule.value or ""
        elif rule.action == "remove":
            next_headers.pop(rule.header, None)
        elif rule.action == "append":
            existing = next_headers.get(rule.header, "")
            joined = f"{existing}, {rule.value}" if existing else (rule.value or "")
            next_headers[rule.header] = joined
    return next_headers


@dataclass
class HeaderTampering:
    """Track a list of rules and attach to a Playwright page."""

    rules: List[HeaderRule] = field(default_factory=list)

    def set_header(self, header: str, value: str,
                   url_substring: Optional[str] = None,
                   name: Optional[str] = None) -> HeaderRule:
        rule = HeaderRule(
            name=name or f"set:{header}",
            header=header,
            action="set",
            value=value,
            url_match=re.compile(re.escape(url_substring)) if url_substring else None,
        )
        self.rules.append(rule)
        return rule

    def remove_header(self, header: str,
                      url_substring: Optional[str] = None) -> HeaderRule:
        rule = HeaderRule(
            name=f"remove:{header}",
            header=header,
            action="remove",
            url_match=re.compile(re.escape(url_substring)) if url_substring else None,
        )
        self.rules.append(rule)
        return rule

    def attach_to_page(self, page: Any) -> None:
        """Wire the rules onto a Playwright page via ``page.route('**/*')``."""
        if not hasattr(page, "route"):
            raise HeaderTamperingError("page does not expose route() — Playwright only")

        rules = self.rules

        def _handler(route: Any, request: Any) -> None:
            url = getattr(request, "url", "")
            base_headers = dict(getattr(request, "headers", {}) or {})
            mutated = apply_to_request_headers(base_headers, url, rules)
            web_runner_logger.debug(
                f"header_tampering url={url[:80]} added/changed={set(mutated) - set(base_headers)}"
            )
            try:
                route.continue_(headers=mutated)
            except Exception as error:  # pylint: disable=broad-except
                web_runner_logger.warning(
                    f"header_tampering continue_ failed: {error!r}"
                )
                route.continue_()

        page.route("**/*", _handler)
