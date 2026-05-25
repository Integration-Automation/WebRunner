"""
Email deliverability header audit.

For every test that triggers a transactional email, this module checks
the captured raw message (or just the headers) for the three modern
sender-authentication signals:

* **SPF** — ``Received-SPF: pass`` or ``Authentication-Results: ...
  spf=pass`` from the receiving relay.
* **DKIM** — at least one ``DKIM-Signature: v=1; ...`` header AND an
  ``Authentication-Results`` line saying ``dkim=pass``.
* **DMARC** — the ``Authentication-Results`` line says ``dmarc=pass``
  and ``policy.dmarc=`` matches the expected policy.

Optionally validates `List-Unsubscribe` and `List-Unsubscribe-Post`
(Gmail/Yahoo bulk-sender rules from Feb 2024).
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException


class EmailDeliverabilityError(WebRunnerException):
    """Raised when a deliverability invariant is violated."""


@dataclass
class HeaderMap:
    """All headers as a case-insensitive multimap (header → list of values)."""

    headers: Dict[str, List[str]] = field(default_factory=dict)

    def get_all(self, name: str) -> List[str]:
        return list(self.headers.get(name.lower(), []))

    def get_first(self, name: str) -> Optional[str]:
        all_ = self.get_all(name)
        return all_[0] if all_ else None


def parse_headers(raw: str) -> HeaderMap:
    """Parse RFC 5322 headers (lines, continuations) from a raw message."""
    if not isinstance(raw, str):
        raise EmailDeliverabilityError("raw must be a string")
    out: Dict[str, List[str]] = {}
    cur_name: Optional[str] = None
    cur_value: List[str] = []
    for line in raw.splitlines():
        if not line.strip():
            break   # end of headers
        if line[:1] in (" ", "\t") and cur_name:
            cur_value.append(line.strip())
            continue
        if cur_name is not None:
            out.setdefault(cur_name, []).append(" ".join(cur_value).strip())
        name, _, val = line.partition(":")
        cur_name = name.lower().strip()
        cur_value = [val.strip()]
    if cur_name is not None:
        out.setdefault(cur_name, []).append(" ".join(cur_value).strip())
    return HeaderMap(headers=out)


def _auth_results_says(headers: HeaderMap, mechanism: str, status: str) -> bool:
    pattern = re.compile(rf"\b{re.escape(mechanism)}\s*=\s*{re.escape(status)}\b",
                         re.IGNORECASE)
    return any(pattern.search(line)
               for line in headers.get_all("Authentication-Results"))


def assert_spf_pass(headers: HeaderMap) -> None:
    if _auth_results_says(headers, "spf", "pass"):
        return
    received_spf = headers.get_first("Received-SPF") or ""
    if not received_spf.lower().startswith("pass"):
        raise EmailDeliverabilityError(
            "no SPF=pass found in Authentication-Results or Received-SPF"
        )


def assert_dkim_pass(headers: HeaderMap) -> None:
    if not headers.get_all("DKIM-Signature"):
        raise EmailDeliverabilityError(
            "message has no DKIM-Signature header"
        )
    if not _auth_results_says(headers, "dkim", "pass"):
        raise EmailDeliverabilityError(
            "DKIM-Signature present but Authentication-Results "
            "does not say dkim=pass"
        )


def assert_dmarc_pass(headers: HeaderMap, *, expected_policy: str = "") -> None:
    if not _auth_results_says(headers, "dmarc", "pass"):
        raise EmailDeliverabilityError(
            "no dmarc=pass in Authentication-Results"
        )
    if expected_policy:
        pattern = re.compile(
            rf"policy\.dmarc\s*=\s*{re.escape(expected_policy)}\b",
            re.IGNORECASE,
        )
        if not any(pattern.search(line)
                   for line in headers.get_all("Authentication-Results")):
            raise EmailDeliverabilityError(
                f"DMARC policy doesn't match expected={expected_policy!r}"
            )


def assert_list_unsubscribe(headers: HeaderMap) -> None:
    """Gmail / Yahoo bulk sender rules (Feb 2024) require
    ``List-Unsubscribe`` + ``List-Unsubscribe-Post``."""
    if not headers.get_first("List-Unsubscribe"):
        raise EmailDeliverabilityError(
            "missing List-Unsubscribe header (Gmail/Yahoo bulk requirement)"
        )
    post = headers.get_first("List-Unsubscribe-Post") or ""
    if "List-Unsubscribe=One-Click" not in post:
        raise EmailDeliverabilityError(
            "List-Unsubscribe-Post must contain 'List-Unsubscribe=One-Click' "
            "(RFC 8058 one-click unsubscribe)"
        )


def assert_no_bcc_leak(headers: HeaderMap) -> None:
    """Sanity: BCC must be stripped before delivery."""
    if headers.get_first("Bcc"):
        raise EmailDeliverabilityError(
            "Bcc header leaked into delivered message"
        )
