"""
儀表板頁面的共用元件 / Building blocks shared by the dashboard pages.

Every helper escapes the values it is given, so a page only ever concatenates the
strings these return. Attributes use single quotes throughout, and ``html_escape``
escapes both quote characters.
"""
from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import Any, Iterable
from urllib.parse import urlparse

NAV = (
    ("/", "Overview"),
    ("/runs", "Runs"),
    ("/flake", "Flake"),
    ("/quarantine", "Quarantine"),
    ("/locators", "Locators"),
    ("/schedule", "Schedule"),
    ("/triage", "Triage"),
)


def html_escape(value: Any) -> str:
    """Escape ``value`` for HTML text and quoted attributes (``None`` becomes empty)."""
    return html.escape(str(value if value is not None else ""), quote=True)


def layout(title: str, body: str, *, active: str = "") -> str:
    """
    頁面外框：head、樣式與腳本、導覽列
    Wrap ``body`` in the page chrome. ``active`` is the path of the nav entry to mark
    with ``aria-current``; the header shows when the page was rendered.
    """
    links = "".join(
        f"<a href='{href}'" + (" aria-current='page'" if href == active else "") + f">{label}</a>"
        for href, label in NAV
    )
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return (
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>{html_escape(title)} — WebRunner</title>"
        "<link rel='icon' href='/static/favicon.svg' type='image/svg+xml'>"
        "<link rel='stylesheet' href='/static/app.css'>"
        "<script src='/static/app.js' defer></script></head><body>"
        "<header class='top'><div class='top-inner'><span class='brand'>WebRunner</span>"
        f"<nav aria-label='Dashboard pages'>{links}</nav>"
        f"<div class='live'><span>Updated <time id='updated' datetime='{now}'>{now}</time></span>"
        "<span id='live-status' class='muted'></span>"
        "<button id='live-toggle' type='button' hidden aria-pressed='false'>Pause</button>"
        f"</div></div></header><main>{body}</main></body></html>"
    )


def card(label: str, value: Any, status: str = "") -> str:
    """One summary card; ``status`` is ``good`` / ``warn`` / ``bad`` or empty."""
    return (
        f"<div class='card {html_escape(status)}'><div class='label'>{html_escape(label)}</div>"
        f"<div class='value'>{html_escape(value)}</div></div>"
    )


def cards(items: Iterable[tuple[str, Any, str]]) -> str:
    """A grid of :func:`card` entries from ``(label, value, status)`` tuples."""
    return "<div class='cards'>" + "".join(card(*item) for item in items) + "</div>"


def empty(message: str, hint: str = "") -> str:
    """An empty-state box, with an optional hint on how to get data."""
    hint_html = f"<span class='hint'>{html_escape(hint)}</span>" if hint else ""
    return f"<div class='empty'>{html_escape(message)}{hint_html}</div>"


def badge(text: str, status: str) -> str:
    """A small coloured label (``good`` / ``warn`` / ``bad``)."""
    return f"<span class='badge {html_escape(status)}'>{html_escape(text)}</span>"


def time_tag(value: Any) -> str:
    """A ``<time>`` the script shows in local time; a dash when there is no value."""
    if not value:
        return "<span class='muted'>—</span>"
    text = html_escape(value)
    return f"<time datetime='{text}'>{text}</time>"


def number(value: Any, digits: int = 2) -> str:
    """``value`` rounded for display; non-numbers are shown as a dash."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "—"
    return f"{value:.{digits}f}" if isinstance(value, float) else str(value)


def meter(value: Any, *, maximum: float = 1.0, higher_is_better: bool = True) -> str:
    """A ``<meter>`` bar plus the number; non-numbers render as a dash."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "<span class='muted'>—</span>"
    # A score is fine from 80 % of the scale up; a rate of trouble (flakiness, fallbacks)
    # is a warning from 20 % and bad from 50 %.
    low, high = (0.5 * maximum, 0.8 * maximum) if higher_is_better else (0.2 * maximum, 0.5 * maximum)
    optimum = maximum if higher_is_better else 0
    return (
        f"<meter min='0' max='{maximum}' low='{low}' high='{high}' optimum='{optimum}' "
        f"value='{value}'></meter>{html_escape(number(value))}"
    )


def safe_link(url: Any, text: str) -> str:
    """A link for ``http``/``https`` URLs only; anything else (``javascript:`` …) is plain text."""
    if not isinstance(url, str) or urlparse(url).scheme not in {"http", "https"}:
        return html_escape(url) if url else "<span class='muted'>—</span>"
    return f"<a href='{html_escape(url)}' rel='noopener noreferrer' target='_blank'>{html_escape(text)}</a>"


def live(region_id: str, content: str) -> str:
    """A region the page refresh replaces with the server's fresh copy (matched by ``id``)."""
    return f"<div id='{region_id}' data-live>{content}</div>"


def data_table(
    table_id: str,
    headers: Iterable[tuple[str, str]],
    rows: list[str],
    *,
    empty_state: str,
    status_filter: bool = False,
) -> str:
    """
    可排序、可篩選的表格
    A sortable table with a filter box (and a pass/fail selector when ``status_filter``).
    ``headers`` are ``(label, css_class)``; ``rows`` are ready ``<tr>`` strings, and
    ``empty_state`` is shown instead when there are none. Table or empty state sit in a
    :func:`live` region, so the page refresh swaps them while the toolbar keeps its input.
    """
    status_select = (
        f"<select data-status-filter='{table_id}' aria-label='Result'>"
        "<option value=''>All results</option><option value='pass'>Passed</option>"
        "<option value='fail'>Failed</option></select>"
        if status_filter else ""
    )
    toolbar = (
        "<div class='toolbar'>"
        f"<input type='search' data-filter='{table_id}' placeholder='Filter…' aria-label='Filter rows'>"
        f"{status_select}<span class='count' data-count='{table_id}'>{len(rows)} rows</span></div>"
    )
    head = "".join(f"<th class='{css}'>{html_escape(label)}</th>" for label, css in headers)
    body = (
        f"<div class='panel'><table id='{table_id}' data-sortable><thead><tr>{head}</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>"
        if rows else empty_state
    )
    return toolbar + live(f"{table_id}-live", body)
