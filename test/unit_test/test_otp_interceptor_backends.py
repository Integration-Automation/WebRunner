"""
Extra unit tests for otp_interceptor backends that the main test file does
not exercise: the HTTP helper, the IMAP provider, raw-email parsing, time
parsing and the provider error branches. All use injection points
(``connector`` / ``http_fetcher`` / monkeypatched urlopen) — no network.
"""
import time
import urllib.request
from email.message import EmailMessage

import pytest

from je_web_runner.utils.otp_interceptor.interceptor import (
    ImapProvider,
    InMemoryProvider,
    MailHogProvider,
    MailpitProvider,
    OtpInterceptError,
    WebhookSmsProvider,
    _http_get_json,
    _imap_bytes_to_message,
    _parse_time,
    wait_for_otp,
)


class _FakeResponse:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def read(self) -> bytes:
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


# ---------- _http_get_json ----------------------------------------------

def test_http_get_json_rejects_non_http():
    with pytest.raises(OtpInterceptError):
        _http_get_json("ftp://example/x")  # NOSONAR S5332 — test fixture URL, not a real transport


def test_http_get_json_parses_json(monkeypatch):
    monkeypatch.setattr(
        urllib.request, "urlopen", lambda *a, **k: _FakeResponse(b'{"ok": 1}')
    )
    assert _http_get_json("http://localhost/api") == {"ok": 1}


def test_http_get_json_empty_body_returns_none(monkeypatch):
    monkeypatch.setattr(
        urllib.request, "urlopen", lambda *a, **k: _FakeResponse(b"")
    )
    assert _http_get_json("http://localhost/api") is None


def test_http_get_json_non_json_raises(monkeypatch):
    monkeypatch.setattr(
        urllib.request, "urlopen", lambda *a, **k: _FakeResponse(b"<html>")
    )
    with pytest.raises(OtpInterceptError):
        _http_get_json("http://localhost/api")


def test_http_get_json_oserror_raises(monkeypatch):
    def boom(*_a, **_k):
        raise OSError("connection refused")

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    with pytest.raises(OtpInterceptError):
        _http_get_json("https://localhost/api")


# ---------- _parse_time --------------------------------------------------

def test_parse_time_none_is_now():
    before = time.time()
    assert _parse_time(None) >= before


def test_parse_time_numeric_passthrough():
    assert _parse_time(1234) == 1234.0  # NOSONAR S1244 — exact numeric passthrough, not a computed float
    assert _parse_time(99.5) == 99.5  # NOSONAR S1244 — exact numeric passthrough, not a computed float


def test_parse_time_iso_with_z():
    assert _parse_time("2026-05-24T10:00:00Z") > 0


def test_parse_time_naive_iso_assumed_utc():
    assert _parse_time("2026-05-24T10:00:00") > 0


def test_parse_time_invalid_string_is_now():
    before = time.time()
    assert _parse_time("not-a-date") >= before


# ---------- IMAP ---------------------------------------------------------

def _email_bytes(*, multipart: bool = False) -> bytes:
    msg = EmailMessage()
    msg["From"] = "bot@example"
    msg["To"] = "user@example"
    msg["Subject"] = "Your login code"
    msg["Date"] = "Sun, 24 May 2026 10:00:00 +0000"
    if multipart:
        msg.set_content("Your code is 112233")
        msg.add_alternative("<p>112233</p>", subtype="html")
    else:
        msg.set_content("Your code is 246810")
    return msg.as_bytes()


class _FakeImapConn:
    def __init__(self, raw: bytes) -> None:
        self._raw = raw
        self.logged_out = False

    def login(self, _user, _password):
        return ("OK", [b"ok"])

    def select(self, _mailbox):
        return ("OK", [b"1"])

    def search(self, _charset, _criteria):
        return ("OK", [b"1"])

    def fetch(self, raw_id, _spec):
        return ("OK", [(raw_id + b" (RFC822 {0}", self._raw)])

    def close(self):
        return ("OK", [b"closed"])

    def logout(self):
        self.logged_out = True
        return ("BYE", [b"bye"])


def test_imap_provider_fetches_and_extracts():
    conn = _FakeImapConn(_email_bytes())
    provider = ImapProvider(
        "imap.example", username="u", password="p",  # NOSONAR S2068 — test fixture credential, not a real secret
        connector=lambda _host, _port: conn,
    )
    messages = provider.fetch_messages(recipient="user@example")
    assert len(messages) == 1
    assert "246810" in messages[0].body
    assert messages[0].subject == "Your login code"
    assert conn.logged_out  # _close_quietly ran logout


def test_imap_provider_requires_credentials():
    with pytest.raises(OtpInterceptError):
        ImapProvider("host", username="", password="p")  # NOSONAR S2068 — test fixture credential, not a real secret
    with pytest.raises(OtpInterceptError):
        ImapProvider("", username="u", password="p")  # NOSONAR S2068 — test fixture credential, not a real secret


def test_imap_bytes_simple_message():
    out = _imap_bytes_to_message("7", _email_bytes())
    assert out is not None
    assert "246810" in out.body
    assert out.sender == "bot@example"


def test_imap_bytes_multipart_prefers_plain():
    out = _imap_bytes_to_message("8", _email_bytes(multipart=True))
    assert out is not None
    assert "112233" in out.body


# ---------- provider error branches -------------------------------------

def test_mailhog_items_not_list_returns_empty():
    provider = MailHogProvider("http://x", http_fetcher=lambda _u: {"items": "nope"})  # NOSONAR S5332 — test fixture URL, not a real transport
    assert provider.fetch_messages() == []


def test_mailhog_skips_non_dict_items():
    provider = MailHogProvider(
        "http://x", http_fetcher=lambda _u: {"items": ["bad", 123]}  # NOSONAR S5332 — test fixture URL, not a real transport
    )
    assert provider.fetch_messages() == []


def test_mailpit_non_dict_payload_raises():
    provider = MailpitProvider("http://x", http_fetcher=lambda _u: [])  # NOSONAR S5332 — test fixture URL, not a real transport
    with pytest.raises(OtpInterceptError):
        provider.fetch_messages()


def test_webhook_sms_filters_by_since():
    rows = [
        {"id": "old", "to": "+1", "body": "code 111111", "received_at": 10.0},
        {"id": "new", "to": "+1", "body": "code 222222", "received_at": 30.0},
    ]
    provider = WebhookSmsProvider("http://sms", http_fetcher=lambda _u: rows)  # NOSONAR S5332 — test fixture URL, not a real transport
    out = provider.fetch_messages(recipient="+1", since=20.0)
    assert [m.message_id for m in out] == ["new"]


# ---------- wait arg validation -----------------------------------------

@pytest.mark.parametrize("kwargs", [
    {"recipient": ""},
    {"recipient": "a@x", "timeout": 0},
    {"recipient": "a@x", "poll_interval": 0},
])
def test_wait_for_otp_validates_args(kwargs):
    recipient = kwargs.pop("recipient")
    with pytest.raises(OtpInterceptError):
        wait_for_otp(InMemoryProvider(), recipient, **kwargs)
