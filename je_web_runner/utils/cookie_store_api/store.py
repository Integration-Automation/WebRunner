"""
Async ``cookieStore`` API helper:harvest + assert + subscribe / change-event
觀測。補 ``cookie_consent`` 缺的事件層 — 用 `document.cookie` 取不到
HttpOnly cookie 也看不到 `change` event。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

from je_web_runner.utils.exception.exceptions import WebRunnerException


class CookieStoreApiError(WebRunnerException):
    """Raised on bad payload or failed assertion."""


# ---------- model -------------------------------------------------------

@dataclass(frozen=True)
class CookieRecord:
    """One cookieStore.get() entry."""

    name: str
    value: str
    domain: str | None = None
    path: str = "/"
    secure: bool = True
    same_site: str = "strict"
    expires: int | None = None  # epoch ms

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ChangeEvent:
    """One ``cookiechange`` event observed via cookieStore subscription."""

    changed: list[CookieRecord] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    timestamp_ms: float = 0.0


# ---------- scripts -----------------------------------------------------

GET_ALL_SCRIPT = """
(async function() {
  if (!('cookieStore' in window)) return [];
  return await cookieStore.getAll();
})();
""".strip()


def install_change_listener_script() -> str:
    """Return JS that wires a change-event recorder to ``window.__wr_cs__``."""
    return (
        "(function() {"
        "  if (window.__wr_cs_installed__) return;"
        "  window.__wr_cs_installed__ = true;"
        "  window.__wr_cs__ = [];"
        "  if (!('cookieStore' in window)) return;"
        "  cookieStore.addEventListener('change', function(e) {"
        "    window.__wr_cs__.push({"
        "      changed: (e.changed||[]).map(function(c){return {"
        "        name: c.name, value: c.value, domain: c.domain,"
        "        path: c.path, secure: c.secure, same_site: c.sameSite,"
        "        expires: c.expires"
        "      };}),"
        "      deleted: (e.deleted||[]).map(function(c){return c.name;}),"
        "      timestamp_ms: performance.now()"
        "    });"
        "  });"
        "})();"
    )


HARVEST_CHANGES_SCRIPT = "return window.__wr_cs__ || [];"


# ---------- parsing -----------------------------------------------------

def parse_cookies(payload: Any) -> list[CookieRecord]:
    """Convert ``cookieStore.getAll()`` result to typed records."""
    if not isinstance(payload, list):
        raise CookieStoreApiError(
            f"cookies payload must be list, got {type(payload).__name__}"
        )
    out: list[CookieRecord] = []
    for raw in payload:
        if not isinstance(raw, dict) or "name" not in raw:
            continue
        out.append(CookieRecord(
            name=str(raw["name"]),
            value=str(raw.get("value") or ""),
            domain=raw.get("domain"),
            path=str(raw.get("path") or "/"),
            secure=bool(raw.get("secure", True)),
            same_site=str(raw.get("same_site") or raw.get("sameSite") or "strict"),
            expires=raw.get("expires"),
        ))
    return out


def parse_change_events(payload: Any) -> list[ChangeEvent]:
    """Convert harvested change-event log to typed records."""
    if not isinstance(payload, list):
        raise CookieStoreApiError(
            f"change events payload must be list, got {type(payload).__name__}"
        )
    out: list[ChangeEvent] = []
    for raw in payload:
        if not isinstance(raw, dict):
            continue
        out.append(ChangeEvent(
            changed=parse_cookies(raw.get("changed") or []),
            deleted=[str(d) for d in (raw.get("deleted") or [])],
            timestamp_ms=float(raw.get("timestamp_ms") or 0.0),
        ))
    return out


# ---------- assertions --------------------------------------------------

def assert_cookie_present(
    cookies: Iterable[CookieRecord], *, name: str, value: str | None = None,
) -> CookieRecord:
    """Assert a cookie with name (and optional value) is present."""
    if not isinstance(name, str) or not name:
        raise CookieStoreApiError("name must be non-empty string")
    for c in cookies:
        if c.name == name:
            if value is not None and c.value != value:
                raise CookieStoreApiError(
                    f"cookie {name} value is {c.value!r}, want {value!r}"
                )
            return c
    raise CookieStoreApiError(f"cookie {name!r} not present")


def assert_cookie_absent(
    cookies: Iterable[CookieRecord], *, name: str,
) -> None:
    for c in cookies:
        if c.name == name:
            raise CookieStoreApiError(f"cookie {name!r} unexpectedly present")


def assert_change_for(
    events: Iterable[ChangeEvent], *, name: str,
) -> ChangeEvent:
    """Assert at least one change event mentions ``name`` (changed or deleted)."""
    for event in events:
        if any(c.name == name for c in event.changed):
            return event
        if name in event.deleted:
            return event
    raise CookieStoreApiError(
        f"no change event mentions cookie {name!r}"
    )


def assert_secure_only(cookies: Iterable[CookieRecord]) -> None:
    """Assert every cookie has secure=True (HTTPS-only)."""
    insecure = [c.name for c in cookies if not c.secure]
    if insecure:
        raise CookieStoreApiError(
            f"non-secure cookies present: {insecure}"
        )
