"""儀表板的 HTML 頁面 / Server-rendered HTML pages; every dynamic value is escaped."""
from __future__ import annotations

import html
from typing import Any


def html_escape(value: Any) -> str:
    """Escape ``value`` for HTML text and quoted attributes (``None`` becomes empty)."""
    return html.escape(str(value if value is not None else ""), quote=True)


def layout(title: str, body: str) -> str:
    """Wrap ``body`` in the page chrome: head, stylesheet link, navigation."""
    return (
        "<!DOCTYPE html><html><head>"
        f"<meta charset='utf-8'><title>{html_escape(title)} — WebRunner</title>"
        "<link rel='stylesheet' href='/static/app.css'></head><body>"
        "<nav>"
        "<a href='/'>Overview</a>"
        "<a href='/runs'>Runs</a>"
        "<a href='/flake'>Flake</a>"
        "<a href='/quarantine'>Quarantine</a>"
        "<a href='/locators'>Locators</a>"
        "</nav>"
        f"<main>{body}</main></body></html>"
    )


def render_overview(summary: dict[str, Any]) -> str:
    pass_rate_pct = f"{summary['pass_rate'] * 100:.1f}%"
    cards = [
        ("Total runs", summary["total_runs"]),
        ("Pass rate", pass_rate_pct),
        ("Passed", summary["passed"]),
        ("Failed", summary["failed"]),
        ("Flaky tests", summary["flaky_tests"]),
        ("Quarantined", summary["quarantined_tests"]),
        ("Weak locators", summary["weak_locators"]),
        ("Avg locator score", summary["average_locator_score"]),
    ]
    card_html = "".join(
        f"<div class='card'><div class='label'>{html_escape(label)}</div>"
        f"<div class='value'>{html_escape(value)}</div></div>"
        for label, value in cards
    )
    body = (
        "<h1>WebRunner overview</h1>"
        f"<div class='cards'>{card_html}</div>"
    )
    return layout("Overview", body)


def render_runs(runs: list[dict[str, Any]]) -> str:
    if not runs:
        return layout("Runs", "<h1>Runs</h1><div class='empty'>No runs recorded yet.</div>")
    rows = []
    for run in runs:
        cls = "good" if run.get("passed") else "bad"
        label = "PASS" if run.get("passed") else "FAIL"
        rows.append(
            f"<tr><td><code>{html_escape(run.get('path'))}</code></td>"
            f"<td class='{cls}'>{label}</td>"
            f"<td class='muted'>{html_escape(run.get('time', ''))}</td></tr>"
        )
    body = (
        "<h1>Recent runs</h1>"
        "<table><thead><tr><th>Test</th><th>Result</th><th>When</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )
    return layout("Runs", body)


def render_flake(entries: list[dict[str, Any]]) -> str:
    flaky_only = [e for e in entries if e.get("is_flaky")]
    if not flaky_only:
        return layout("Flake", "<h1>Flake leaderboard</h1><div class='empty'>No flaky tests detected.</div>")
    rows = []
    for entry in flaky_only[:50]:
        rows.append(
            f"<tr><td><code>{html_escape(entry.get('path'))}</code></td>"
            f"<td class='bad'>{entry.get('flake_score', 0):.2f}</td>"
            f"<td>{entry.get('runs', 0)}</td>"
            f"<td>{entry.get('fails', 0)}</td>"
            f"<td class='muted'>{html_escape(entry.get('last_run', ''))}</td></tr>"
        )
    body = (
        "<h1>Flake leaderboard</h1>"
        "<table><thead><tr><th>Test</th><th>Score</th>"
        "<th>Runs</th><th>Fails</th><th>Last</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )
    return layout("Flake", body)


def render_quarantine(entries: list[dict[str, Any]]) -> str:
    if not entries:
        return layout("Quarantine", "<h1>Quarantine</h1><div class='empty'>Registry is empty.</div>")
    rows = []
    for entry in entries:
        rows.append(
            f"<tr><td><code>{html_escape(entry.get('test_id'))}</code></td>"
            f"<td>{entry.get('flake_score', 0):.2f}</td>"
            f"<td>{html_escape(entry.get('reason', ''))}</td>"
            f"<td class='muted'>{html_escape(entry.get('quarantined_at', ''))}</td></tr>"
        )
    body = (
        "<h1>Quarantined tests</h1>"
        "<table><thead><tr><th>Test</th><th>Score</th>"
        "<th>Reason</th><th>Since</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )
    return layout("Quarantine", body)


def render_locators(report: dict[str, Any]) -> str:
    if not report:
        return layout("Locators", "<h1>Locators</h1><div class='empty'>No locator report loaded.</div>")
    summary_cards = [
        ("Total", report.get("total", 0)),
        ("Weak", report.get("weak", 0)),
        ("Strong", report.get("strong", 0)),
        ("Avg score", report.get("average_score", 0)),
    ]
    card_html = "".join(
        f"<div class='card'><div class='label'>{html_escape(label)}</div>"
        f"<div class='value'>{html_escape(value)}</div></div>"
        for label, value in summary_cards
    )
    weakest = report.get("weakest") or []
    rows = []
    for entry in weakest[:30]:
        reasons = ", ".join(entry.get("reasons") or []) or "—"
        value = entry.get("value", "")
        if isinstance(value, str) and len(value) > 60:
            value = value[:57] + "…"
        rows.append(
            f"<tr><td><code>{html_escape(entry.get('file_path'))}</code></td>"
            f"<td>{entry.get('action_index', '')}</td>"
            f"<td><code>{html_escape(entry.get('strategy', ''))}</code></td>"
            f"<td><code>{html_escape(value)}</code></td>"
            f"<td>{entry.get('score', 0)}</td>"
            f"<td class='muted'>{html_escape(reasons)}</td></tr>"
        )
    rows_html = (
        "<table><thead><tr><th>File</th><th>Idx</th><th>Strategy</th>"
        "<th>Value</th><th>Score</th><th>Reasons</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
        if rows else "<div class='empty'>No weak locators.</div>"
    )
    body = (
        "<h1>Locator health</h1>"
        f"<div class='cards'>{card_html}</div>"
        "<h2>Weakest</h2>" + rows_html
    )
    return layout("Locators", body)


def render_not_found(path: str) -> str:
    """The 404 page for an unknown ``path``."""
    return layout("Not found", f"<h1>Not found</h1><p>No route for {html_escape(path)}</p>")
