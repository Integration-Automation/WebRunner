"""
攔截應用寄出的 email,渲染 HTML 與跨 client 截圖比對。
Capture outbound mail from MailHog / Mailpit (or a directory of ``.eml``
files), normalise it into a :class:`CapturedEmail`, then optionally render
the HTML body inside multiple width / dark-mode viewport "clients" and
save screenshots for visual diff.

The fetch / render layers are deliberately decoupled:

* :func:`fetch_mailhog`, :func:`fetch_mailpit`, :func:`load_eml_file` produce
  :class:`CapturedEmail` records — no rendering, no browser needed.
* :func:`render_email_in_viewports` accepts a callable that drives whatever
  browser the user already wired up (Selenium, Playwright, ``cdp`` module).
  This avoids hard-coupling email_render to one browser stack.
"""
from __future__ import annotations

import email
import json
from dataclasses import dataclass, field
from email.message import Message
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Union

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class EmailRenderError(WebRunnerException):
    """Raised on capture-server I/O, malformed EML, or render driver failure."""


# ---------- data ---------------------------------------------------------

@dataclass
class CapturedEmail:
    """One inbox message normalised across providers."""

    message_id: str
    subject: str
    from_addr: str
    to: List[str]
    html_body: Optional[str] = None
    text_body: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    raw: Optional[str] = None

    def has_html(self) -> bool:
        return bool(self.html_body and self.html_body.strip())


@dataclass(frozen=True)
class ViewportProfile:
    """One render target (e.g. 'gmail-desktop', 'apple-mail-dark')."""

    name: str
    width: int
    height: int
    dark_mode: bool = False
    user_agent: Optional[str] = None


DEFAULT_VIEWPORTS: Sequence[ViewportProfile] = (
    ViewportProfile("desktop-light", 800, 1200, dark_mode=False),
    ViewportProfile("desktop-dark", 800, 1200, dark_mode=True),
    ViewportProfile("mobile-light", 390, 844, dark_mode=False),
)


@dataclass
class RenderArtifact:
    """A single render-and-screenshot output."""

    viewport: str
    screenshot_path: Path
    width: int
    height: int


# ---------- helpers ------------------------------------------------------

def _require_requests() -> Any:
    try:
        import requests  # type: ignore[import-not-found]
        return requests
    except ImportError as error:
        raise EmailRenderError(
            "requests is required to fetch from MailHog/Mailpit. "
            "Install: pip install requests"
        ) from error


def _split_addresses(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if v]
    return [part.strip() for part in str(value).split(",") if part.strip()]


def _parse_eml(raw: Union[str, bytes]) -> CapturedEmail:
    if isinstance(raw, bytes):
        msg = email.message_from_bytes(raw)
    else:
        msg = email.message_from_string(raw)
    return _from_message(msg, raw_text=raw if isinstance(raw, str) else raw.decode("utf-8", "replace"))


def _from_message(msg: Message, *, raw_text: Optional[str] = None) -> CapturedEmail:
    html_body: Optional[str] = None
    text_body: Optional[str] = None
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype == "text/html" and html_body is None:
                html_body = _decode_payload(part)
            elif ctype == "text/plain" and text_body is None:
                text_body = _decode_payload(part)
    else:
        body = _decode_payload(msg)
        if msg.get_content_type() == "text/html":
            html_body = body
        else:
            text_body = body
    headers = dict(msg.items())
    return CapturedEmail(
        message_id=str(msg.get("Message-ID", "")),
        subject=str(msg.get("Subject", "")),
        from_addr=str(msg.get("From", "")),
        to=_split_addresses(msg.get("To")),
        html_body=html_body,
        text_body=text_body,
        headers=headers,
        raw=raw_text,
    )


def _decode_payload(part: Message) -> Optional[str]:
    payload = part.get_payload(decode=True)
    if payload is None:
        return None
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except (LookupError, AttributeError):
        return payload.decode("utf-8", errors="replace")


# ---------- fetchers -----------------------------------------------------

def load_eml_file(path: Union[str, Path]) -> CapturedEmail:
    """Parse a single ``.eml`` file."""
    eml_path = Path(path)
    if not eml_path.exists():
        raise EmailRenderError(f"eml file not found: {eml_path}")
    raw = eml_path.read_bytes()
    return _parse_eml(raw)


def load_eml_dir(directory: Union[str, Path]) -> List[CapturedEmail]:
    """Parse every ``.eml`` file in ``directory`` (non-recursive)."""
    dir_path = Path(directory)
    if not dir_path.is_dir():
        raise EmailRenderError(f"eml directory not found: {dir_path}")
    out: List[CapturedEmail] = []
    for child in sorted(dir_path.glob("*.eml")):
        out.append(load_eml_file(child))
    return out


def fetch_mailhog(base_url: str, *, timeout: float = 10.0) -> List[CapturedEmail]:
    """Fetch messages from a MailHog server's ``/api/v2/messages`` endpoint."""
    requests = _require_requests()
    url = base_url.rstrip("/") + "/api/v2/messages"
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as error:
        raise EmailRenderError(f"mailhog fetch failed: {error!r}") from error
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return []
    return [_parse_mailhog_item(item) for item in items if isinstance(item, dict)]


def _parse_mailhog_item(item: Dict[str, Any]) -> CapturedEmail:
    content = item.get("Content") or {}
    headers = content.get("Headers") or {}
    raw_body = content.get("Body") or ""
    # MailHog gives us the raw body; pass it through email module to split parts.
    header_text = "".join(
        f"{name}: {values[0]}\n" if values else "" for name, values in headers.items()
    )
    raw = header_text + "\n" + raw_body
    return _parse_eml(raw)


def fetch_mailpit(base_url: str, *, timeout: float = 10.0, limit: int = 50) -> List[CapturedEmail]:
    """Fetch messages from a Mailpit server's ``/api/v1/messages`` listing."""
    requests = _require_requests()
    list_url = f"{base_url.rstrip('/')}/api/v1/messages?limit={int(limit)}"
    try:
        listing = requests.get(list_url, timeout=timeout)
        listing.raise_for_status()
        listing_payload = listing.json()
    except (requests.RequestException, ValueError) as error:
        raise EmailRenderError(f"mailpit list failed: {error!r}") from error
    ids = []
    if isinstance(listing_payload, dict):
        for entry in listing_payload.get("messages", []) or []:
            if isinstance(entry, dict) and entry.get("ID"):
                ids.append(entry["ID"])
    out: List[CapturedEmail] = []
    for msg_id in ids:
        raw_url = f"{base_url.rstrip('/')}/api/v1/message/{msg_id}/raw"
        try:
            raw_resp = requests.get(raw_url, timeout=timeout)
            raw_resp.raise_for_status()
        except requests.RequestException as error:
            web_runner_logger.warning(f"mailpit raw fetch failed for {msg_id}: {error!r}")
            continue
        out.append(_parse_eml(raw_resp.content))
    return out


# ---------- rendering ----------------------------------------------------

RenderDriver = Callable[[str, ViewportProfile, Path], Path]
"""Signature: ``driver(html, viewport, target_png) -> actual_png_path``."""


def render_email_in_viewports(
    captured: CapturedEmail,
    driver: RenderDriver,
    output_dir: Union[str, Path],
    *,
    viewports: Sequence[ViewportProfile] = DEFAULT_VIEWPORTS,
) -> List[RenderArtifact]:
    """
    Render ``captured.html_body`` in each viewport via ``driver`` and write
    screenshots into ``output_dir``. The driver receives the HTML, viewport
    profile, and a target PNG path; it must return the path of the file it
    actually wrote (so wrappers that pick their own filename still work).
    """
    if not captured.has_html():
        raise EmailRenderError(f"captured email has no HTML body: {captured.message_id!r}")
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    artifacts: List[RenderArtifact] = []
    for viewport in viewports:
        target = out_dir / f"{_safe_slug(captured.message_id) or 'msg'}__{viewport.name}.png"
        written = Path(driver(captured.html_body or "", viewport, target))
        artifacts.append(RenderArtifact(
            viewport=viewport.name,
            screenshot_path=written,
            width=viewport.width,
            height=viewport.height,
        ))
    return artifacts


def _safe_slug(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in value)
    return cleaned.strip("_")[:80]


# ---------- assertions ---------------------------------------------------

def assert_subject_contains(captured: CapturedEmail, needle: str) -> None:
    """Raise unless ``needle`` is a substring of the captured subject."""
    if not isinstance(needle, str) or not needle:
        raise EmailRenderError("needle must be a non-empty string")
    if needle not in (captured.subject or ""):
        raise EmailRenderError(
            f"subject does not contain {needle!r}: actual={captured.subject!r}"
        )


def export_summary_json(
    captures: Sequence[CapturedEmail],
    output_path: Union[str, Path],
) -> Path:
    """Persist a compact JSON list of captured emails for downstream tooling."""
    payload = [
        {
            "message_id": c.message_id,
            "subject": c.subject,
            "from": c.from_addr,
            "to": c.to,
            "has_html": c.has_html(),
        }
        for c in captures
    ]
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False, indent=2)
    return path
