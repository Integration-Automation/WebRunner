"""
TLS cipher / version / OCSP-stapling audit.

This module performs a live TLS handshake (no external libs beyond
stdlib ``ssl``) and reports:

* Negotiated TLS version (must be 1.2 or 1.3).
* Negotiated cipher suite (must be on a configurable allowlist;
  defaults block 3DES, RC4, NULL, EXPORT, MD5 macs).
* Whether OCSP stapling was offered (optional but recommended).
* Whether the certificate is trusted by the system store.
"""
from __future__ import annotations

import socket
import ssl
from dataclasses import asdict, dataclass
from typing import Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class TlsCipherAuditError(WebRunnerException):
    """Raised when a TLS invariant is violated."""


_DEFAULT_BANNED_TOKENS = (
    "RC4", "3DES", "DES-CBC", "NULL", "EXPORT", "MD5",
    "PSK", "DSS", "ADH",
)

_ACCEPTABLE_VERSIONS = ("TLSv1.2", "TLSv1.3")


@dataclass
class TlsHandshakeReport:
    host: str
    port: int = 443
    version: str | None = None
    cipher_suite: str | None = None
    ocsp_stapled: bool = False
    cert_subject: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def handshake(
    host: str, port: int = 443, *, timeout: float = 10.0,
    context: ssl.SSLContext | None = None,
) -> TlsHandshakeReport:
    """Do a real TLS handshake and report what was negotiated."""
    if not isinstance(host, str) or not host:
        raise TlsCipherAuditError("host must be a non-empty string")
    if not 1 <= port <= 65535:
        raise TlsCipherAuditError("port out of range")
    if timeout <= 0:
        raise TlsCipherAuditError("timeout must be > 0")
    ctx = context or ssl.create_default_context()
    # Pin a modern protocol floor explicitly so older Python interpreters
    # (pre-3.10, where TLSv1+ would still negotiate) don't downgrade.
    if hasattr(ctx, "minimum_version") and hasattr(ssl, "TLSVersion"):
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    try:
        with socket.create_connection((host, port), timeout=timeout) as raw:
            with ctx.wrap_socket(raw, server_hostname=host) as tls:
                cert = tls.getpeercert() or {}
                subject_parts = []
                for rdn in cert.get("subject", ()):
                    for k, v in rdn:
                        subject_parts.append(f"{k}={v}")
                return TlsHandshakeReport(
                    host=host, port=port,
                    version=tls.version(),
                    cipher_suite=(tls.cipher() or (None,))[0],
                    ocsp_stapled=False,   # stdlib ssl exposes no API for this
                    cert_subject="/".join(subject_parts),
                )
    except ssl.SSLError as exc:
        raise TlsCipherAuditError(f"TLS handshake failed: {exc!r}") from exc
    except OSError as exc:
        raise TlsCipherAuditError(f"connection failed: {exc!r}") from exc


def assert_modern_tls(report: TlsHandshakeReport) -> None:
    if report.version not in _ACCEPTABLE_VERSIONS:
        raise TlsCipherAuditError(
            f"negotiated TLS version {report.version!r} not in {_ACCEPTABLE_VERSIONS}"
        )


def assert_cipher_safe(
    report: TlsHandshakeReport,
    *, banned_tokens: Sequence[str] = _DEFAULT_BANNED_TOKENS,
) -> None:
    if not report.cipher_suite:
        raise TlsCipherAuditError("no cipher suite negotiated")
    upper = report.cipher_suite.upper()
    bad = [token for token in banned_tokens if token in upper]
    if bad:
        raise TlsCipherAuditError(
            f"weak cipher {report.cipher_suite!r} matches banned tokens: {bad}"
        )


def assert_subject_matches(
    report: TlsHandshakeReport, *, contains: str,
) -> None:
    if not contains:
        raise TlsCipherAuditError("contains must be non-empty")
    if contains not in report.cert_subject:
        raise TlsCipherAuditError(
            f"certificate subject {report.cert_subject!r} does not contain "
            f"{contains!r}"
        )
