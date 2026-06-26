"""
OTP / Email / SMS 攔截器：整合 MailHog / Mailpit / IMAP / 自建 webhook,
讓 E2E 測試可以等待並抽取一次性驗證碼,不再卡在 2FA 流程。

OTP interception backends shared by a single
:func:`wait_for_otp` helper. Built-in providers:

* :class:`MailHogProvider`    — http://mailhog/api/v2 style inbox
* :class:`MailpitProvider`    — http://mailpit/api/v1 style inbox
* :class:`ImapProvider`       — production-style IMAP fetch
* :class:`WebhookSmsProvider` — local SMS webhook (e.g. Twilio sandbox
                                 forwarder)
* :class:`InMemoryProvider`   — for offline tests and dry-runs

Providers expose a single :meth:`fetch_messages` method that returns a
list of :class:`InterceptedMessage` newest-first. Polling logic and
regex extraction are implemented once in :func:`wait_for_otp`.
"""
from __future__ import annotations

import json
import re
import ssl
import time
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Pattern, Union

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class OtpInterceptError(WebRunnerException):
    """Raised on provider config / fetch / extraction problems."""


# ---------- data ----------------------------------------------------------

@dataclass
class InterceptedMessage:
    """One email / SMS message normalised across providers."""

    message_id: str
    sender: str
    recipient: str
    subject: str
    body: str
    received_at: float
    headers: Dict[str, str] = field(default_factory=dict)


# ---------- abstract provider --------------------------------------------

class OtpProvider(ABC):
    """Base class — concrete providers normalise raw inbox data."""

    @abstractmethod
    def fetch_messages(
        self,
        recipient: Optional[str] = None,
        *,
        since: Optional[float] = None,
        limit: int = 25,
    ) -> List[InterceptedMessage]:
        """Return messages newest-first, optionally filtered by recipient/since."""


# ---------- HTTP helper --------------------------------------------------

def _http_get_json(url: str, timeout: float = 10.0) -> Any:
    # S5332 ok: MailHog / Mailpit are local-only services that expose plain
    # HTTP REST APIs by design; the caller passes a localhost URL.
    if not url.startswith(("http://", "https://")):
        raise OtpInterceptError(f"refusing non-http URL: {url!r}")
    req = urllib.request.Request(url, method="GET")
    req.add_header("Accept", "application/json")
    if url.startswith("http://"):
        context = None  # plain HTTP for local MailHog / Mailpit
    else:
        context = ssl.create_default_context()
        context.minimum_version = ssl.TLSVersion.TLSv1_2
    try:
        with urllib.request.urlopen(  # nosec B310 — scheme allow-listed
            req, timeout=timeout, context=context,
        ) as response:
            body = response.read().decode("utf-8")
    except (OSError, ValueError) as error:
        raise OtpInterceptError(f"HTTP GET failed for {url}: {error!r}") from error
    if not body:
        return None
    try:
        return json.loads(body)
    except ValueError as error:
        raise OtpInterceptError(f"non-JSON response from {url}: {error}") from error


# ---------- MailHog ------------------------------------------------------

class MailHogProvider(OtpProvider):
    """Talks to a MailHog ``/api/v2/messages`` endpoint."""

    def __init__(self, base_url: str, *, http_fetcher: Optional[Callable[[str], Any]] = None) -> None:
        self.base_url = base_url.rstrip("/")
        self._fetch = http_fetcher or _http_get_json

    def fetch_messages(
        self,
        recipient: Optional[str] = None,
        *,
        since: Optional[float] = None,
        limit: int = 25,
    ) -> List[InterceptedMessage]:
        url = f"{self.base_url}/api/v2/messages?limit={limit}"
        payload = self._fetch(url)
        if not isinstance(payload, dict):
            raise OtpInterceptError("MailHog payload is not an object")
        items = payload.get("items")
        if not isinstance(items, list):
            return []
        out: List[InterceptedMessage] = []
        for raw in items:
            msg = _mailhog_to_message(raw)
            if msg is None:
                continue
            if recipient and msg.recipient.lower() != recipient.lower():
                continue
            if since and msg.received_at < since:
                continue
            out.append(msg)
        out.sort(key=lambda m: m.received_at, reverse=True)
        return out


def _mailhog_to_message(raw: Any) -> Optional[InterceptedMessage]:
    if not isinstance(raw, dict):
        return None
    content = raw.get("Content") or {}
    headers = content.get("Headers") or {}
    from_list = headers.get("From") or []
    to_list = headers.get("To") or []
    subject_list = headers.get("Subject") or []
    message_id = raw.get("ID") or ""
    body = content.get("Body") or ""
    received_at = _parse_time(raw.get("Created"))
    return InterceptedMessage(
        message_id=str(message_id),
        sender=from_list[0] if from_list else "",
        recipient=to_list[0] if to_list else "",
        subject=subject_list[0] if subject_list else "",
        body=str(body),
        received_at=received_at,
        headers={k: ", ".join(v) if isinstance(v, list) else str(v) for k, v in headers.items()},
    )


# ---------- Mailpit ------------------------------------------------------

class MailpitProvider(OtpProvider):
    """Talks to a Mailpit ``/api/v1/messages`` endpoint."""

    def __init__(self, base_url: str, *, http_fetcher: Optional[Callable[[str], Any]] = None) -> None:
        self.base_url = base_url.rstrip("/")
        self._fetch = http_fetcher or _http_get_json

    def fetch_messages(
        self,
        recipient: Optional[str] = None,
        *,
        since: Optional[float] = None,
        limit: int = 25,
    ) -> List[InterceptedMessage]:
        url = f"{self.base_url}/api/v1/messages?limit={limit}"
        payload = self._fetch(url)
        if not isinstance(payload, dict):
            raise OtpInterceptError("Mailpit payload is not an object")
        items = payload.get("messages") or payload.get("Messages") or []
        if not isinstance(items, list):
            return []
        out: List[InterceptedMessage] = []
        for raw in items:
            msg = _mailpit_to_message(raw)
            if msg is None:
                continue
            if recipient and msg.recipient.lower() != recipient.lower():
                continue
            if since and msg.received_at < since:
                continue
            out.append(msg)
        out.sort(key=lambda m: m.received_at, reverse=True)
        return out


def _mailpit_to_message(raw: Any) -> Optional[InterceptedMessage]:
    if not isinstance(raw, dict):
        return None
    to_list = raw.get("To") or []
    first_to = to_list[0] if to_list else {}
    return InterceptedMessage(
        message_id=str(raw.get("ID") or ""),
        sender=str((raw.get("From") or {}).get("Address") or ""),
        recipient=str(first_to.get("Address") if isinstance(first_to, dict) else first_to),
        subject=str(raw.get("Subject") or ""),
        body=str(raw.get("Text") or raw.get("Snippet") or ""),
        received_at=_parse_time(raw.get("Created")),
    )


# ---------- IMAP ---------------------------------------------------------

class ImapProvider(OtpProvider):
    """Real IMAP fetch — used when MailHog/Mailpit isn't available."""

    def __init__(
        self,
        host: str,
        port: int = 993,
        *,
        username: str,
        password: str,
        mailbox: str = "INBOX",
        use_ssl: bool = True,
        connector: Optional[Callable[..., Any]] = None,
    ) -> None:
        if not host or not username or not password:
            raise OtpInterceptError("IMAP host/username/password are all required")
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.mailbox = mailbox
        self.use_ssl = use_ssl
        self._connector = connector

    def _connect(self):  # NOSONAR S3776 — cohesive logic; planned refactor in follow-up
        if self._connector is not None:
            return self._connector(self.host, self.port)
        import imaplib  # local import — IMAP is rarely needed
        return (imaplib.IMAP4_SSL if self.use_ssl else imaplib.IMAP4)(self.host, self.port)

    def _fetch_one(self, conn: Any, raw_id: bytes, since: Optional[float]) -> Optional[InterceptedMessage]:
        _typ, msg_data = conn.fetch(raw_id, "(RFC822)")
        if not msg_data or not msg_data[0]:
            return None
        payload = msg_data[0]
        raw_bytes = payload[1] if isinstance(payload, tuple) else payload
        msg = _imap_bytes_to_message(raw_id.decode(), raw_bytes)
        if msg is None:
            return None
        if since and msg.received_at < since:
            return None
        return msg

    def _close_quietly(self, conn: Any) -> None:
        for method_name in ("close", "logout"):
            try:
                getattr(conn, method_name)()
            except Exception:  # nosec B110 — best-effort cleanup
                pass

    def fetch_messages(
        self,
        recipient: Optional[str] = None,
        *,
        since: Optional[float] = None,
        limit: int = 25,
    ) -> List[InterceptedMessage]:
        conn = self._connect()
        try:
            conn.login(self.username, self.password)
            conn.select(self.mailbox)
            criteria = "ALL" if not recipient else f'(TO "{recipient}")'
            _typ, ids_data = conn.search(None, criteria)
            ids = (ids_data[0].split() if ids_data and ids_data[0] else [])[-limit:]
            messages: List[InterceptedMessage] = []
            for raw_id in reversed(ids):
                msg = self._fetch_one(conn, raw_id, since)
                if msg is not None:
                    messages.append(msg)
            return messages
        finally:
            self._close_quietly(conn)


def _imap_bytes_to_message(message_id: str, raw_bytes: bytes) -> Optional[InterceptedMessage]:
    import email
    from email import policy

    try:
        msg = email.message_from_bytes(raw_bytes, policy=policy.default)
    except Exception:
        return None
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                body = part.get_content()
                break
    else:
        try:
            body = msg.get_content()
        except Exception:
            body = ""
    return InterceptedMessage(
        message_id=message_id,
        sender=str(msg.get("From") or ""),
        recipient=str(msg.get("To") or ""),
        subject=str(msg.get("Subject") or ""),
        body=str(body),
        received_at=_parse_time(msg.get("Date")),
        headers=dict(msg.items()),
    )


# ---------- SMS webhook --------------------------------------------------

class WebhookSmsProvider(OtpProvider):
    """
    Poll a local webhook that aggregates SMS into a list endpoint
    (``GET /messages?to=+15551234567``). Useful with Twilio sandbox or
    a self-hosted bridge.
    """

    def __init__(
        self,
        base_url: str,
        *,
        endpoint: str = "/messages",
        http_fetcher: Optional[Callable[[str], Any]] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.endpoint = "/" + endpoint.lstrip("/")
        self._fetch = http_fetcher or _http_get_json

    def fetch_messages(
        self,
        recipient: Optional[str] = None,
        *,
        since: Optional[float] = None,
        limit: int = 25,
    ) -> List[InterceptedMessage]:
        query = f"limit={limit}"
        if recipient:
            query += "&to=" + urllib.parse.quote(recipient, safe="")
        url = f"{self.base_url}{self.endpoint}?{query}"
        payload = self._fetch(url)
        if not isinstance(payload, list):
            raise OtpInterceptError("SMS webhook payload must be a JSON list")
        out: List[InterceptedMessage] = []
        for raw in payload:
            if not isinstance(raw, dict):
                continue
            msg = InterceptedMessage(
                message_id=str(raw.get("id") or raw.get("sid") or ""),
                sender=str(raw.get("from") or ""),
                recipient=str(raw.get("to") or ""),
                subject="",
                body=str(raw.get("body") or raw.get("text") or ""),
                received_at=_parse_time(raw.get("received_at") or raw.get("created_at")),
            )
            if since and msg.received_at < since:
                continue
            out.append(msg)
        out.sort(key=lambda m: m.received_at, reverse=True)
        return out


# ---------- in-memory (for tests) ----------------------------------------

class InMemoryProvider(OtpProvider):
    """Tests and dry-runs: hand it a list of messages."""

    def __init__(self) -> None:
        self.messages: List[InterceptedMessage] = []

    def push(self, message: InterceptedMessage) -> None:
        self.messages.append(message)

    def clear(self) -> None:
        self.messages.clear()

    def fetch_messages(
        self,
        recipient: Optional[str] = None,
        *,
        since: Optional[float] = None,
        limit: int = 25,
    ) -> List[InterceptedMessage]:
        out = list(self.messages)
        if recipient:
            out = [m for m in out if m.recipient.lower() == recipient.lower()]
        if since:
            out = [m for m in out if m.received_at >= since]
        out.sort(key=lambda m: m.received_at, reverse=True)
        return out[:limit]


# ---------- time parsing -------------------------------------------------

def _parse_time(value: Any) -> float:
    if value is None:
        return time.time()
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value:
        # ISO-8601: 2026-05-24T10:00:00Z or 2026-05-24T10:00:00.000Z
        from datetime import datetime, timezone

        text = value
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except ValueError:
            return time.time()
    return time.time()


# ---------- OTP extraction & polling -------------------------------------

_DEFAULT_OTP_REGEX = re.compile(r"\b(\d{4,8})\b")


def extract_otp_from_text(
    text: str,
    pattern: Union[str, Pattern[str], None] = None,
) -> Optional[str]:
    """
    從文字中抽出 OTP code。預設 4–8 位數字。
    Apply ``pattern`` (defaults to 4–8 digits) and return the first match.
    Returns ``None`` when no match is found.
    """
    if not isinstance(text, str) or not text:
        return None
    if pattern is None:
        regex: Pattern[str] = _DEFAULT_OTP_REGEX
    elif isinstance(pattern, str):
        regex = re.compile(pattern)
    else:
        regex = pattern
    match = regex.search(text)
    if match is None:
        return None
    if match.groups():
        return match.group(1)
    return match.group(0)


def _otp_match(
    msg: InterceptedMessage,
    *,
    subject_contains: Optional[str],
    pattern: Union[str, Pattern[str], None],
) -> Optional[str]:
    if subject_contains and subject_contains.lower() not in msg.subject.lower():
        return None
    return (
        extract_otp_from_text(msg.body, pattern)
        or extract_otp_from_text(msg.subject, pattern)
    )


def _validate_wait_args(
    provider: OtpProvider, recipient: str, timeout: float, poll_interval: float,
) -> None:
    if not isinstance(provider, OtpProvider):
        raise OtpInterceptError(f"provider must be an OtpProvider, got {type(provider).__name__}")
    if not recipient:
        raise OtpInterceptError("recipient is required")
    if timeout <= 0:
        raise OtpInterceptError("timeout must be positive")
    if poll_interval <= 0:
        raise OtpInterceptError("poll_interval must be positive")


def wait_for_otp(
    provider: OtpProvider,
    recipient: str,
    *,
    pattern: Union[str, Pattern[str], None] = None,
    timeout: float = 30.0,
    poll_interval: float = 1.0,
    since: Optional[float] = None,
    subject_contains: Optional[str] = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    time_fn: Callable[[], float] = time.time,
) -> str:
    """
    輪詢 provider 直到收到含 OTP 的訊息或 timeout。
    Poll the provider every ``poll_interval`` seconds until a message that
    matches ``recipient`` (and optionally ``subject_contains``) arrives AND
    contains an OTP matching ``pattern``. Returns the extracted OTP string.

    Raises :class:`OtpInterceptError` on timeout. ``since`` defaults to
    "now" so messages already in the inbox don't accidentally match.
    """
    _validate_wait_args(provider, recipient, timeout, poll_interval)
    start = time_fn()
    if since is None:
        since = start
    while True:
        messages = provider.fetch_messages(recipient=recipient, since=since)
        for msg in messages:
            code = _otp_match(msg, subject_contains=subject_contains, pattern=pattern)
            if code:
                web_runner_logger.info(
                    f"wait_for_otp: matched {recipient} subject={msg.subject!r}"
                )
                return code
        if time_fn() - start >= timeout:
            raise OtpInterceptError(
                f"timeout waiting for OTP for {recipient!r} after {timeout}s"
            )
        sleep_fn(poll_interval)
