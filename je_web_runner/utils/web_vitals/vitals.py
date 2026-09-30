"""
Core Web Vitals 預算斷言 / One budget assertion for the Core Web Vitals: LCP, CLS, INP, FCP.

Two sources:

* ``page`` measures the live page of whichever backend is running (Selenium, else
  Playwright): LCP, CLS and FCP with the ``perf_metrics`` collector, INP from the
  ``inp_tracker`` event-timing log. The browser buffers event entries of 104 ms or more,
  so interactions before the call still count; INP is None when there were none.
* ``lighthouse`` runs Lighthouse on a URL and reads its lab audits. A navigation has no
  interactions, so Lighthouse reports Total Blocking Time (``tbt``) instead of INP.

Each metric is rated against Google's thresholds (good / needs-improvement / poor) and
compared with the budget, which defaults to the "good" limit; a metric that could not be
measured is reported, not failed. A breach explains itself with the diagnostics the source
gives: the LCP element, the elements whose shifts added the most to CLS, the slowest
interaction.
"""
from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.inp_tracker.tracker import HARVEST_SCRIPT, InpReport, build_install_script, parse_log
from je_web_runner.utils.lighthouse.lighthouse_runner import run_lighthouse
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.utils.perf_metrics.page_metrics import playwright_collect_metrics, selenium_collect_metrics
from je_web_runner.webdriver.playwright_wrapper import PlaywrightBackendError, playwright_wrapper_instance
from je_web_runner.webdriver.webdriver_wrapper import webdriver_wrapper_instance

# Google's thresholds: at or under GOOD is good, over POOR is poor.
GOOD = {"lcp": 2500.0, "cls": 0.1, "inp": 200.0, "fcp": 1800.0, "tbt": 200.0}
POOR = {"lcp": 4000.0, "cls": 0.25, "inp": 500.0, "fcp": 3000.0, "tbt": 600.0}
_LIGHTHOUSE_AUDITS = {"lcp": "largest-contentful-paint", "cls": "cumulative-layout-shift",
                      "fcp": "first-contentful-paint", "tbt": "total-blocking-time"}


class WebVitalsError(WebRunnerException):
    """A metric is over its budget, or the vitals could not be measured."""


def rate(metric: str, value: float) -> str:
    """``good``, ``needs-improvement`` or ``poor`` by Google's thresholds for ``metric``."""
    if value <= GOOD[metric]:
        return "good"
    return "needs-improvement" if value <= POOR[metric] else "poor"


def _slowest_interaction(report: InpReport) -> dict[str, Any] | None:
    """The slowest interaction: its event types, the first target any of them names, its duration.

    One click is several entries (pointerdown, pointerup, click) sharing an interaction id;
    some browsers leave the pointer entries without a target.
    """
    interactions = report.filtered()
    if not interactions:
        return None
    slowest = max(interactions, key=lambda event: event.duration_ms)
    same = [event for event in interactions if event.interaction_id == slowest.interaction_id]
    return {"events": sorted({event.name for event in same}),
            "target": next((event.target_tag for event in same if event.target_tag), None),
            "duration_ms": slowest.duration_ms}


def _measure_with(collect: Any, run_script: Any, observe_ms: int, source: str, url: str) -> dict[str, Any]:
    run_script(build_install_script())  # buffered: interactions before this still count
    raw = collect(observe_ms) or {}
    report = InpReport(parse_log(run_script(HARVEST_SCRIPT) or []))
    return {
        "source": source, "url": url,
        "metrics": {"lcp": raw.get("lcp"), "cls": raw.get("cls"), "inp": report.inp(), "fcp": raw.get("fcp")},
        "diagnostics": {"lcp_element": raw.get("lcp_element"), "lcp_url": raw.get("lcp_url"),
                        "cls_sources": raw.get("cls_sources") or [],
                        "slowest_interaction": _slowest_interaction(report)},
    }


def measure_page(observe_ms: int = 1000) -> dict[str, Any]:
    """
    量測目前頁面（Selenium 優先，其次 Playwright）
    Measure the current page of the running backend: Selenium when a driver is running,
    else the Playwright page. Returns ``{source, url, metrics, diagnostics}``.
    """
    driver = webdriver_wrapper_instance.current_webdriver
    if driver is not None:
        return _measure_with(selenium_collect_metrics, driver.execute_script, observe_ms,
                             "selenium", driver.current_url)
    try:
        page = playwright_wrapper_instance.page
    except PlaywrightBackendError as error:
        raise WebVitalsError("no Selenium driver or Playwright page is running") from error
    return _measure_with(playwright_collect_metrics, _playwright_script_runner(page), observe_ms,
                         "playwright", page.url)


def _playwright_script_runner(page: Any) -> Any:
    """Run a Selenium-style script (a ``return`` statement or an IIFE) on a Playwright page."""
    def run(script: str) -> Any:
        body = script.strip().rstrip(";")
        return page.evaluate(f"() => {{ {body if body.startswith('return') else 'return ' + body} }}")
    return run


def _first_selector(value: Any) -> str | None:
    """The first ``node.selector`` anywhere in a Lighthouse audit's details."""
    pending = [value]
    while pending:
        item = pending.pop(0)
        if isinstance(item, dict):
            node = item.get("node")
            if isinstance(node, dict) and isinstance(node.get("selector"), str):
                return node["selector"]
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)
    return None


def lighthouse_measurement(url: str, report: dict[str, Any]) -> dict[str, Any]:
    """``{source, url, metrics, diagnostics}`` from a Lighthouse JSON report."""
    audits = report.get("audits") or {}
    metrics: dict[str, Any] = {"inp": None}
    for metric, audit in _LIGHTHOUSE_AUDITS.items():
        value = (audits.get(audit) or {}).get("numericValue")
        metrics[metric] = float(value) if isinstance(value, (int, float)) else None
    return {
        "source": "lighthouse", "url": url, "metrics": metrics,
        "diagnostics": {"lcp_element": _first_selector(audits.get("largest-contentful-paint-element")),
                        "cls_sources": [selector for selector in [
                            _first_selector(audits.get("layout-shifts") or audits.get("layout-shift-elements"))]
                            if selector]},
    }


def evaluate(measurement: dict[str, Any], budgets: dict[str, float] | None = None) -> dict[str, Any]:
    """
    依預算評估量測結果
    Rate and budget every metric in ``measurement``. ``budgets`` overrides the "good"
    limits per metric (``{"lcp": 3000}``). Returns ``{passed, source, url, metrics:
    [{metric, value, budget, rating, status}], diagnostics}``; ``status`` is ``pass``,
    ``fail`` or ``not measured``.
    """
    limits = dict(GOOD)
    unknown = set(budgets or {}) - set(GOOD)
    if unknown:
        raise WebVitalsError(f"unknown metrics in budgets: {sorted(unknown)}; use {sorted(GOOD)}")
    limits.update({key: float(value) for key, value in (budgets or {}).items()})
    rows = []
    for metric, value in measurement["metrics"].items():
        if value is None:
            rows.append({"metric": metric, "value": None, "budget": limits[metric], "rating": None,
                         "status": "not measured"})
            continue
        rows.append({"metric": metric, "value": value, "budget": limits[metric], "rating": rate(metric, value),
                     "status": "pass" if value <= limits[metric] else "fail"})
    return {"passed": all(row["status"] != "fail" for row in rows), "source": measurement["source"],
            "url": measurement["url"], "metrics": rows, "diagnostics": measurement["diagnostics"]}


def write_reports(result: dict[str, Any], json_path: str | None = None, html_path: str | None = None) -> None:
    """Write the evaluated result as JSON and / or a standalone HTML table (every value escaped)."""
    if json_path:
        Path(json_path).parent.mkdir(parents=True, exist_ok=True)
        Path(json_path).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if html_path:
        Path(html_path).parent.mkdir(parents=True, exist_ok=True)
        Path(html_path).write_text(_html(result), encoding="utf-8")


def _html(result: dict[str, Any]) -> str:
    cells = "".join(
        f"<tr class='{html.escape(row['status'].replace(' ', '-'))}'><td>{html.escape(row['metric'].upper())}</td>"
        f"<td>{html.escape(_shown(row['value']))}</td><td>{html.escape(_shown(row['budget']))}</td>"
        f"<td>{html.escape(row['rating'] or '')}</td><td>{html.escape(row['status'])}</td></tr>"
        for row in result["metrics"])
    diagnostics = html.escape(json.dumps(result["diagnostics"], ensure_ascii=False, indent=2))
    verdict = "passed" if result["passed"] else "failed"
    return (
        "<!doctype html><html><head><meta charset='utf-8'><title>Web Vitals</title><style>"
        "body{font-family:sans-serif;margin:24px}table{border-collapse:collapse}td,th{border:1px solid #ccc;"
        "padding:4px 10px;text-align:left}.fail{background:#fde2e1}.pass{background:#e3f6e8}</style></head><body>"
        f"<h1>Web Vitals: {verdict}</h1><p>{html.escape(result['source'])}: {html.escape(str(result['url']))}</p>"
        "<table><tr><th>Metric</th><th>Value</th><th>Budget</th><th>Rating</th><th>Status</th></tr>"
        f"{cells}</table><h2>Diagnostics</h2><pre>{diagnostics}</pre></body></html>"
    )


def _shown(value: Any) -> str:
    """A metric value for a report: ``—`` when missing, floats without trailing zeros."""
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.3f}".rstrip("0").rstrip(".")
    return str(value)


def assert_web_vitals(budgets: dict[str, float] | None = None, observe_ms: int = 1000, source: str = "page",
                      url: str | None = None, json_path: str | None = None, html_path: str | None = None,
                      lighthouse_path: str = "lighthouse") -> dict[str, Any]:
    """
    斷言 LCP / CLS / INP / FCP 都在預算內
    Measure the Core Web Vitals (``source`` ``page`` or ``lighthouse``; Lighthouse needs
    ``url``), rate and budget them, write the breakdown to ``json_path`` / ``html_path``
    when given, and return it. Raises :class:`WebVitalsError` naming every metric over
    budget with its rating and the diagnostics.
    """
    if source == "page":
        measurement = measure_page(observe_ms)
    elif source == "lighthouse":
        if not url:
            raise WebVitalsError("source='lighthouse' needs a url")
        measurement = lighthouse_measurement(url, run_lighthouse(url, lighthouse_path=lighthouse_path)["raw"])
    else:
        raise WebVitalsError(f"source must be 'page' or 'lighthouse', got {source!r}")
    result = evaluate(measurement, budgets)
    write_reports(result, json_path, html_path)
    web_runner_logger.info(f"assert_web_vitals: {'passed' if result['passed'] else 'failed'} ({result['url']})")
    if not result["passed"]:
        breaches = "; ".join(
            f"{row['metric'].upper()} {_shown(row['value'])} > {_shown(row['budget'])} ({row['rating']})"
            for row in result["metrics"] if row["status"] == "fail")
        raise WebVitalsError(f"web vitals over budget: {breaches}; diagnostics: {result['diagnostics']}")
    return result
