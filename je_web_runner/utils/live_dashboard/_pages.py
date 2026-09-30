"""
儀表板的 HTML 頁面 / Server-rendered HTML pages.

Every page works without JavaScript; ``/static/app.js`` adds local times, sorting,
filtering and the live refresh on top. Dynamic values only reach a page through the
escaping helpers in :mod:`._widgets`.
"""
from __future__ import annotations

from typing import Any

from je_web_runner.utils.live_dashboard._charts import pass_rate_chart
from je_web_runner.utils.live_dashboard._widgets import (
    badge,
    cards,
    data_table,
    empty,
    html_escape,
    layout,
    live,
    meter,
    number,
    safe_link,
    time_tag,
)

_CONFIG_HINT = "Pass its path in DashboardConfig({field}=...) when starting the dashboard."
_RUNS_STEP = 50
_RUNS_MAX = 5000


def _rate_status(rate: float, total: int) -> str:
    if not total:
        return ""
    if rate >= 0.95:
        return "good"
    return "warn" if rate >= 0.8 else "bad"


def _count_status(count: Any, bad_when_positive: str, has_data: bool) -> str:
    if not has_data:
        return ""
    return bad_when_positive if isinstance(count, (int, float)) and count > 0 else "good"


def _run_row(run: dict[str, Any]) -> str:
    passed = bool(run.get("passed"))
    result = badge("PASS", "good") if passed else badge("FAIL", "bad")
    return (
        f"<tr data-status='{'pass' if passed else 'fail'}'>"
        f"<td><code>{html_escape(run.get('path'))}</code></td><td>{result}</td>"
        f"<td data-sort='{html_escape(run.get('time', ''))}'>{time_tag(run.get('time'))}</td></tr>"
    )


def render_overview(summary: dict[str, Any], daily: list[dict[str, Any]], recent: list[dict[str, Any]]) -> str:
    """Summary cards, the daily pass-rate chart and the latest runs."""
    total = summary["total_runs"]
    has_runs = bool(total)
    summary_cards = cards([
        ("Total runs", total, ""),
        ("Pass rate", f"{summary['pass_rate'] * 100:.1f}%", _rate_status(summary["pass_rate"], total)),
        ("Passed", summary["passed"], "good" if has_runs else ""),
        ("Failed", summary["failed"], _count_status(summary["failed"], "bad", has_runs)),
        ("Flaky tests", summary["flaky_tests"], _count_status(summary["flaky_tests"], "warn", has_runs)),
        ("Quarantined", summary["quarantined_tests"], _count_status(summary["quarantined_tests"], "warn", True)),
        ("Weak locators", summary["weak_locators"], _count_status(summary["weak_locators"], "warn", True)),
        ("Avg locator score", number(summary["average_locator_score"], 1), ""),
    ])
    chart = pass_rate_chart(daily)
    chart_html = (
        f"<div class='panel padded'>{chart}<div class='legend'><span><span class='key line'></span>"
        "Pass rate</span><span><span class='key fail'></span>Failures</span></div></div>"
        if chart else empty("No dated runs to chart yet.")
    )
    recent_html = (
        "<div class='panel'><table><thead><tr><th>Test</th><th>Result</th><th>When</th></tr></thead>"
        f"<tbody>{''.join(_run_row(run) for run in recent)}</tbody></table></div>"
        "<a class='more' href='/runs'>All runs</a>"
        if recent else empty("No runs recorded yet.", _CONFIG_HINT.format(field="ledger_path"))
    )
    body = (
        "<h1>WebRunner overview</h1>"
        + live("overview-live", f"{summary_cards}<h2>Pass rate by day</h2>{chart_html}"
                                f"<h2>Latest runs</h2>{recent_html}")
    )
    return layout("Overview", body, active="/")


def render_runs(runs: list[dict[str, Any]], total: int, limit: int) -> str:
    """The newest ``limit`` runs with a result filter, and a link to show more."""
    more = ""
    if total > len(runs) and limit < _RUNS_MAX:
        more = f"<a class='more' href='/runs?limit={min(limit + _RUNS_STEP, _RUNS_MAX)}'>Show more</a>"
    table = data_table(
        "runs", [("Test", ""), ("Result", ""), ("When", "")],
        [_run_row(run) for run in runs],
        empty_state=empty("No runs recorded yet.", _CONFIG_HINT.format(field="ledger_path")),
        status_filter=True,
    )
    heading = "<h1>Recent runs</h1>" + live(
        "runs-summary", f"<p class='muted'>Showing {len(runs)} of {total} runs, newest first.</p>")
    return layout("Runs", heading + table + live("runs-more", more), active="/runs")


def _flake_row(entry: dict[str, Any]) -> str:
    score = entry.get("flake_score")
    pass_rate = entry.get("pass_rate")
    rate_text = f"{pass_rate * 100:.1f}%" if isinstance(pass_rate, (int, float)) else "—"
    return (
        f"<tr><td><code>{html_escape(entry.get('path'))}</code></td>"
        f"<td data-sort='{html_escape(score)}'>{meter(score, higher_is_better=False)}</td>"
        f"<td class='num' data-sort='{html_escape(pass_rate)}'>{rate_text}</td>"
        f"<td class='num'>{html_escape(entry.get('runs', 0))}</td>"
        f"<td class='num'>{html_escape(entry.get('fails', 0))}</td>"
        f"<td data-sort='{html_escape(entry.get('last_run', ''))}'>{time_tag(entry.get('last_run'))}</td></tr>"
    )


def render_flake(entries: list[dict[str, Any]]) -> str:
    """Every test flagged flaky, most flaky first."""
    flaky = [entry for entry in entries if entry.get("is_flaky")]
    table = data_table(
        "flake",
        [("Test", ""), ("Flake score", ""), ("Pass rate", "num"), ("Runs", "num"), ("Fails", "num"), ("Last run", "")],
        [_flake_row(entry) for entry in flaky],
        empty_state=empty("No flaky tests detected.", "A test is flaky when it both passes and fails "
                                                      "often enough in the ledger."),
    )
    heading = "<h1>Flake leaderboard</h1>" + live(
        "flake-summary", f"<p class='muted'>{len(flaky)} flaky of {len(entries)} tests in the ledger; "
                         "the score weights recent failures more.</p>")
    return layout("Flake", heading + table, active="/flake")


def _quarantine_row(entry: dict[str, Any]) -> str:
    score = entry.get("flake_score")
    return (
        f"<tr><td><code>{html_escape(entry.get('test_id'))}</code></td>"
        f"<td data-sort='{html_escape(score)}'>{meter(score, higher_is_better=False)}</td>"
        f"<td>{html_escape(entry.get('reason', ''))}</td>"
        f"<td data-sort='{html_escape(entry.get('quarantined_at', ''))}'>{time_tag(entry.get('quarantined_at'))}</td>"
        f"<td class='num'>{html_escape(entry.get('runs_when_added', 0))}</td>"
        f"<td>{safe_link(entry.get('triage_url'), 'Triage')}</td></tr>"
    )


def render_quarantine(entries: list[dict[str, Any]]) -> str:
    """The quarantine registry: why and since when each test is quarantined."""
    table = data_table(
        "quarantine",
        [("Test", ""), ("Score", ""), ("Reason", ""), ("Since", ""), ("Runs when added", "num"), ("Triage", "")],
        [_quarantine_row(entry) for entry in entries],
        empty_state=empty("Registry is empty.", _CONFIG_HINT.format(field="quarantine_path")),
    )
    return layout("Quarantine", "<h1>Quarantined tests</h1>" + table, active="/quarantine")


def _locator_row(entry: dict[str, Any]) -> str:
    value = entry.get("value", "")
    shown = value[:57] + "…" if isinstance(value, str) and len(value) > 60 else value
    reasons = ", ".join(str(reason) for reason in entry.get("reasons") or []) or "—"
    return (
        f"<tr><td><code>{html_escape(entry.get('file_path'))}</code></td>"
        f"<td class='num'>{html_escape(entry.get('action_index', ''))}</td>"
        f"<td><code>{html_escape(entry.get('strategy', ''))}</code></td>"
        f"<td><code title='{html_escape(value)}'>{html_escape(shown)}</code></td>"
        f"<td data-sort='{html_escape(entry.get('score', 0))}'>"
        f"{meter(entry.get('score'), maximum=100)}</td>"
        f"<td class='muted'>{html_escape(reasons)}</td></tr>"
    )


def _offender_row(entry: dict[str, Any]) -> str:
    rate = entry.get("fallback_rate")
    return (
        f"<tr><td><code>{html_escape(entry.get('file_path'))}</code></td>"
        f"<td><code>{html_escape(entry.get('name') or entry.get('value', ''))}</code></td>"
        f"<td class='num'>{html_escape(entry.get('hits', 0))}</td>"
        f"<td class='num'>{html_escape(entry.get('fallback_used', 0))}</td>"
        f"<td data-sort='{html_escape(rate)}'>{meter(rate, higher_is_better=False)}</td></tr>"
    )


def render_locators(report: dict[str, Any]) -> str:
    """Locator health: summary cards, the weakest locators, and fallback offenders."""
    if not report:
        return layout("Locators", "<h1>Locators</h1>" + live("locators-live", empty(
            "No locator report loaded.", _CONFIG_HINT.format(field="locator_findings_path"))), active="/locators")
    weak = report.get("weak", 0)
    summary_cards = cards([
        ("Total", report.get("total", 0), ""),
        ("Weak", weak, _count_status(weak, "warn", True)),
        ("Strong", report.get("strong", 0), ""),
        ("Avg score", number(report.get("average_score", 0), 1), ""),
        ("Threshold", report.get("threshold", "—"), ""),
    ])
    weakest = data_table(
        "weakest", [("File", ""), ("Idx", "num"), ("Strategy", ""), ("Value", ""), ("Score", ""), ("Reasons", "")],
        [_locator_row(entry) for entry in report.get("weakest") or []],
        empty_state=empty("No weak locators."),
    )
    offenders = data_table(
        "offenders", [("File", ""), ("Locator", ""), ("Hits", "num"), ("Fallback used", "num"), ("Fallback rate", "")],
        [_offender_row(entry) for entry in report.get("fallback_offenders") or []],
        empty_state=empty("No locator needed its self-healing fallback.", "Filled in when the run "
                                                                          "tracks fallback hits."),
    )
    body = (
        "<h1>Locator health</h1>" + live("locators-live", summary_cards)
        + "<h2>Weakest</h2>" + weakest + "<h2>Fallback offenders</h2>" + offenders
    )
    return layout("Locators", body, active="/locators")


def _code_list(table_id: str, heading: str, items: list[Any]) -> str:
    return data_table(table_id, [(heading, "")],
                      [f"<tr><td><code>{html_escape(item)}</code></td></tr>" for item in items],
                      empty_state=empty(f"No {heading.lower()} tests."))


def render_schedule(schedule: dict[str, Any]) -> str:
    """The test scheduler's plan: what fits the time and cloud budget and what was left out."""
    if not schedule:
        return layout("Schedule", "<h1>Schedule</h1>" + live("schedule-live", empty(
            "No schedule loaded.", _CONFIG_HINT.format(field="schedule_path"))), active="/schedule")
    selected = list(schedule.get("selected") or [])
    skipped = list(schedule.get("skipped") or [])
    summary_cards = cards([
        ("Selected", len(selected), "good" if selected else ""),
        ("Skipped", len(skipped), "warn" if skipped else "good"),
        ("Planned seconds", number(schedule.get("total_seconds"), 1), ""),
        ("Cloud slots", schedule.get("total_cloud_slots", "—"), ""),
        ("Seconds left", number(schedule.get("leftover_seconds"), 1), ""),
        ("Value recovered", number(schedule.get("value_recovered"), 2), ""),
    ])
    body = (
        "<h1>Schedule</h1>" + live("schedule-live", summary_cards)
        + "<h2>Selected</h2>" + _code_list("selected", "Selected", selected)
        + "<h2>Skipped</h2>" + _code_list("skipped", "Skipped", skipped)
    )
    return layout("Schedule", body, active="/schedule")


def _item_list(tag: str, items: Any) -> str:
    if not isinstance(items, list) or not items:
        return "<span class='muted'>—</span>"
    return f"<{tag}>" + "".join(f"<li>{html_escape(item)}</li>" for item in items) + f"</{tag}>"


def _triage_panel(report: dict[str, Any]) -> str:
    confidence = report.get("confidence")
    category = report.get("category") or "unknown"
    return (
        "<div class='panel padded'><dl class='facts'>"
        f"<dt>Test</dt><dd><code>{html_escape(report.get('test_name') or '—')}</code></dd>"
        f"<dt>Category</dt><dd>{badge(category, 'warn' if category != 'unknown' else '')}</dd>"
        f"<dt>Confidence</dt><dd>{meter(confidence)}</dd>"
        f"<dt>Likely cause</dt><dd>{html_escape(report.get('likely_cause') or '—')}</dd>"
        f"<dt>Suggested fix</dt><dd>{html_escape(report.get('suggested_fix') or '—')}</dd>"
        f"<dt>Evidence</dt><dd>{_item_list('ul', report.get('evidence'))}</dd>"
        f"<dt>Next steps</dt><dd>{_item_list('ol', report.get('next_steps'))}</dd>"
        f"<dt>Error signature</dt><dd><code>{html_escape(report.get('error_signature') or '—')}</code></dd>"
        "</dl></div>"
    )


def render_triage(triage: Any) -> str:
    """One failure-triage report, or a list of them."""
    reports = triage if isinstance(triage, list) else [triage] if triage else []
    reports = [report for report in reports if isinstance(report, dict)]
    content = (
        "<div class='stack'>" + "".join(_triage_panel(report) for report in reports) + "</div>"
        if reports else empty("No triage report loaded.", _CONFIG_HINT.format(field="triage_report_path"))
    )
    return layout("Triage", "<h1>Failure triage</h1>" + live("triage-live", content), active="/triage")


def render_not_found(path: str) -> str:
    """The 404 page for an unknown ``path``."""
    return layout("Not found", f"<h1>Not found</h1><p>No route for {html_escape(path)}</p>")
