"""
Live Dashboard:把既有 run_ledger / flake_detector / locator_health /
failure_triage / test_scheduler / quarantine registry 的資料整合在一個
本地 web UI。

純 stdlib(``http.server``),不加新依賴。預設只 bind 127.0.0.1,
單 process,跟 socket_server 共存無干擾。

Routes:

* ``GET /``               HTML overview with summary cards
* ``GET /runs``           HTML table of recent ledger entries
* ``GET /flake``          HTML flake leaderboard
* ``GET /quarantine``     HTML quarantine list
* ``GET /locators``       HTML locator health summary
* ``GET /api/summary``    JSON aggregate counts
* ``GET /api/runs``       JSON recent runs (``?limit=N``)
* ``GET /api/flake``      JSON flake scores
* ``GET /api/quarantine`` JSON quarantine entries
* ``GET /api/locators``   JSON locator findings

Every request re-reads the underlying files so the dashboard always
reflects the latest state — no caching, no daemon process needed.
"""
from __future__ import annotations

import json
import threading
import urllib.parse
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type, Union

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.flake_detector.detector import (
    QuarantineRegistry,
    compute_flake_scores,
)
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.utils.run_ledger.ledger import LedgerError


class LiveDashboardError(WebRunnerException):
    """Raised on configuration / startup failures."""


# ---------- config -------------------------------------------------------

@dataclass
class DashboardConfig:
    """
    指定每個資料來源檔案路徑。任何一個 None 就會在 UI 上顯示成空白。
    """
    ledger_path: Optional[Union[str, Path]] = None
    quarantine_path: Optional[Union[str, Path]] = None
    locator_findings_path: Optional[Union[str, Path]] = None
    schedule_path: Optional[Union[str, Path]] = None
    triage_report_path: Optional[Union[str, Path]] = None
    bind_host: str = "127.0.0.1"
    bind_port: int = 0

    def __post_init__(self) -> None:
        for attr in (
            "ledger_path", "quarantine_path", "locator_findings_path",
            "schedule_path", "triage_report_path",
        ):
            value = getattr(self, attr)
            if value is not None and not isinstance(value, Path):
                setattr(self, attr, Path(value))


# ---------- data loaders -------------------------------------------------

def _load_runs(ledger_path: Optional[Path], limit: int = 50) -> List[Dict[str, Any]]:
    if ledger_path is None or not ledger_path.exists():
        return []
    try:
        with open(ledger_path, encoding="utf-8") as fp:
            data = json.load(fp)
    except (OSError, ValueError) as error:
        web_runner_logger.warning(f"dashboard _load_runs: {error!r}")
        return []
    runs = data.get("runs") if isinstance(data, dict) else None
    if not isinstance(runs, list):
        return []
    return [r for r in runs[-limit:][::-1] if isinstance(r, dict)]


def _load_flake_scores(ledger_path: Optional[Path]) -> List[Dict[str, Any]]:
    if ledger_path is None or not ledger_path.exists():
        return []
    try:
        scores = compute_flake_scores(ledger_path)
    except (LedgerError, OSError, ValueError) as error:
        web_runner_logger.warning(f"dashboard _load_flake_scores: {error!r}")
        return []
    entries = [s.to_dict() for s in scores.values()]
    entries.sort(key=lambda e: (-e["flake_score"], e["path"]))
    return entries


def _load_quarantine(quarantine_path: Optional[Path]) -> List[Dict[str, Any]]:
    if quarantine_path is None or not quarantine_path.exists():
        return []
    try:
        registry = QuarantineRegistry(quarantine_path)
    except WebRunnerException as error:
        web_runner_logger.warning(f"dashboard _load_quarantine: {error!r}")
        return []
    return [e.to_dict() for e in registry.list()]


def _load_locator_report(path: Optional[Path]) -> Dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as fp:
            return json.load(fp)
    except (OSError, ValueError) as error:
        web_runner_logger.warning(f"dashboard _load_locator_report: {error!r}")
        return {}


def _load_schedule(path: Optional[Path]) -> Dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as fp:
            return json.load(fp)
    except (OSError, ValueError) as error:
        web_runner_logger.warning(f"dashboard _load_schedule: {error!r}")
        return {}


def _load_triage(path: Optional[Path]) -> Dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as fp:
            return json.load(fp)
    except (OSError, ValueError) as error:
        web_runner_logger.warning(f"dashboard _load_triage: {error!r}")
        return {}


# ---------- summary ------------------------------------------------------

def build_summary(config: DashboardConfig) -> Dict[str, Any]:
    """One-shot snapshot used by ``/`` and ``/api/summary``."""
    runs = _load_runs(config.ledger_path, limit=10_000)
    total = len(runs)
    passed = sum(1 for r in runs if r.get("passed"))
    failed = total - passed
    pass_rate = (passed / total) if total else 0.0
    flake_entries = _load_flake_scores(config.ledger_path)
    flake_count = sum(1 for f in flake_entries if f.get("is_flaky"))
    quarantine = _load_quarantine(config.quarantine_path)
    locator_report = _load_locator_report(config.locator_findings_path)
    return {
        "total_runs": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": round(pass_rate, 4),
        "flaky_tests": flake_count,
        "quarantined_tests": len(quarantine),
        "weak_locators": locator_report.get("weak", 0) if isinstance(locator_report, dict) else 0,
        "average_locator_score": (
            locator_report.get("average_score", 0)
            if isinstance(locator_report, dict) else 0
        ),
    }


# ---------- HTML rendering -----------------------------------------------

_BASE_CSS = """
body { font-family: -apple-system, BlinkMacSystemFont, sans-serif;
       margin: 0; background: #f5f5f7; color: #1d1d1f; }
nav  { background: #1d1d1f; color: #fff; padding: 12px 24px; }
nav a { color: #fff; margin-right: 16px; text-decoration: none; }
nav a:hover { text-decoration: underline; }
main { padding: 24px; max-width: 1200px; margin: 0 auto; }
h1   { margin-top: 0; }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
         gap: 16px; margin-bottom: 32px; }
.card  { background: #fff; padding: 16px; border-radius: 8px;
         box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
.card .label { color: #6e6e73; font-size: 12px; text-transform: uppercase; }
.card .value { font-size: 28px; font-weight: 600; margin-top: 4px; }
table { width: 100%; border-collapse: collapse; background: #fff;
        border-radius: 8px; overflow: hidden;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
th, td { padding: 12px 16px; text-align: left; border-bottom: 1px solid #f0f0f3; }
th { background: #fafafa; font-size: 13px; color: #6e6e73; }
tr:last-child td { border-bottom: none; }
.bad   { color: #c9302c; font-weight: 600; }
.good  { color: #1d8348; font-weight: 600; }
.muted { color: #6e6e73; }
.empty { color: #6e6e73; padding: 32px; text-align: center; }
code   { background: #f0f0f3; padding: 2px 6px; border-radius: 4px;
         font-family: 'SF Mono', Consolas, monospace; font-size: 12px; }
"""


def _html_escape(value: Any) -> str:
    text = str(value if value is not None else "")
    return (
        text.replace("&", "&amp;").replace("<", "&lt;")
        .replace(">", "&gt;").replace('"', "&quot;")
    )


def _layout(title: str, body: str) -> str:
    return (
        "<!DOCTYPE html><html><head>"
        f"<meta charset='utf-8'><title>{_html_escape(title)} — WebRunner</title>"
        f"<style>{_BASE_CSS}</style></head><body>"
        "<nav>"
        "<a href='/'>Overview</a>"
        "<a href='/runs'>Runs</a>"
        "<a href='/flake'>Flake</a>"
        "<a href='/quarantine'>Quarantine</a>"
        "<a href='/locators'>Locators</a>"
        "</nav>"
        f"<main>{body}</main></body></html>"
    )


def _render_overview(summary: Dict[str, Any]) -> str:
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
        f"<div class='card'><div class='label'>{_html_escape(label)}</div>"
        f"<div class='value'>{_html_escape(value)}</div></div>"
        for label, value in cards
    )
    body = (
        "<h1>WebRunner overview</h1>"
        f"<div class='cards'>{card_html}</div>"
    )
    return _layout("Overview", body)


def _render_runs(runs: List[Dict[str, Any]]) -> str:
    if not runs:
        return _layout("Runs", "<h1>Runs</h1><div class='empty'>No runs recorded yet.</div>")
    rows = []
    for run in runs:
        cls = "good" if run.get("passed") else "bad"
        label = "PASS" if run.get("passed") else "FAIL"
        rows.append(
            f"<tr><td><code>{_html_escape(run.get('path'))}</code></td>"
            f"<td class='{cls}'>{label}</td>"
            f"<td class='muted'>{_html_escape(run.get('time', ''))}</td></tr>"
        )
    body = (
        "<h1>Recent runs</h1>"
        "<table><thead><tr><th>Test</th><th>Result</th><th>When</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )
    return _layout("Runs", body)


def _render_flake(entries: List[Dict[str, Any]]) -> str:
    flaky_only = [e for e in entries if e.get("is_flaky")]
    if not flaky_only:
        return _layout("Flake", "<h1>Flake leaderboard</h1><div class='empty'>No flaky tests detected.</div>")
    rows = []
    for entry in flaky_only[:50]:
        rows.append(
            f"<tr><td><code>{_html_escape(entry.get('path'))}</code></td>"
            f"<td class='bad'>{entry.get('flake_score', 0):.2f}</td>"
            f"<td>{entry.get('runs', 0)}</td>"
            f"<td>{entry.get('fails', 0)}</td>"
            f"<td class='muted'>{_html_escape(entry.get('last_run', ''))}</td></tr>"
        )
    body = (
        "<h1>Flake leaderboard</h1>"
        "<table><thead><tr><th>Test</th><th>Score</th>"
        "<th>Runs</th><th>Fails</th><th>Last</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )
    return _layout("Flake", body)


def _render_quarantine(entries: List[Dict[str, Any]]) -> str:
    if not entries:
        return _layout("Quarantine", "<h1>Quarantine</h1><div class='empty'>Registry is empty.</div>")
    rows = []
    for entry in entries:
        rows.append(
            f"<tr><td><code>{_html_escape(entry.get('test_id'))}</code></td>"
            f"<td>{entry.get('flake_score', 0):.2f}</td>"
            f"<td>{_html_escape(entry.get('reason', ''))}</td>"
            f"<td class='muted'>{_html_escape(entry.get('quarantined_at', ''))}</td></tr>"
        )
    body = (
        "<h1>Quarantined tests</h1>"
        "<table><thead><tr><th>Test</th><th>Score</th>"
        "<th>Reason</th><th>Since</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )
    return _layout("Quarantine", body)


def _render_locators(report: Dict[str, Any]) -> str:
    if not report:
        return _layout("Locators", "<h1>Locators</h1><div class='empty'>No locator report loaded.</div>")
    summary_cards = [
        ("Total", report.get("total", 0)),
        ("Weak", report.get("weak", 0)),
        ("Strong", report.get("strong", 0)),
        ("Avg score", report.get("average_score", 0)),
    ]
    card_html = "".join(
        f"<div class='card'><div class='label'>{_html_escape(label)}</div>"
        f"<div class='value'>{_html_escape(value)}</div></div>"
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
            f"<tr><td><code>{_html_escape(entry.get('file_path'))}</code></td>"
            f"<td>{entry.get('action_index', '')}</td>"
            f"<td><code>{_html_escape(entry.get('strategy', ''))}</code></td>"
            f"<td><code>{_html_escape(value)}</code></td>"
            f"<td>{entry.get('score', 0)}</td>"
            f"<td class='muted'>{_html_escape(reasons)}</td></tr>"
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
    return _layout("Locators", body)


# ---------- request handler ---------------------------------------------

def _make_handler(config: DashboardConfig) -> Type[BaseHTTPRequestHandler]:
    """Bind ``config`` into a fresh handler class so each server is isolated."""

    class DashboardHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003 — base override
            web_runner_logger.info(f"dashboard: {fmt % args}")

        def _send(self, status: int, content_type: str, body: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _send_html(self, html: str, status: int = 200) -> None:
            self._send(status, "text/html; charset=utf-8", html.encode("utf-8"))

        def _send_json(self, payload: Any, status: int = 200) -> None:
            body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            self._send(status, "application/json; charset=utf-8", body)

        def _query_limit(self, parsed) -> int:
            params = urllib.parse.parse_qs(parsed.query)
            raw = params.get("limit", ["50"])[0]
            try:
                value = int(raw)
            except ValueError:
                value = 50
            return max(1, min(value, 5000))

        def do_GET(self) -> None:  # noqa: N802 — http.server requires camelCase
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            try:
                if path == "/":
                    self._send_html(_render_overview(build_summary(config)))
                elif path == "/runs":
                    self._send_html(_render_runs(_load_runs(config.ledger_path)))
                elif path == "/flake":
                    self._send_html(_render_flake(_load_flake_scores(config.ledger_path)))
                elif path == "/quarantine":
                    self._send_html(_render_quarantine(_load_quarantine(config.quarantine_path)))
                elif path == "/locators":
                    self._send_html(_render_locators(_load_locator_report(config.locator_findings_path)))
                elif path == "/api/summary":
                    self._send_json(build_summary(config))
                elif path == "/api/runs":
                    self._send_json(_load_runs(config.ledger_path, self._query_limit(parsed)))
                elif path == "/api/flake":
                    self._send_json(_load_flake_scores(config.ledger_path))
                elif path == "/api/quarantine":
                    self._send_json(_load_quarantine(config.quarantine_path))
                elif path == "/api/locators":
                    self._send_json(_load_locator_report(config.locator_findings_path))
                elif path == "/api/schedule":
                    self._send_json(_load_schedule(config.schedule_path))
                elif path == "/api/triage":
                    self._send_json(_load_triage(config.triage_report_path))
                elif path == "/healthz":
                    self._send(200, "text/plain", b"ok")
                else:
                    self._send_html(
                        _layout(
                            "Not found",
                            f"<h1>Not found</h1><p>No route for {_html_escape(path)}</p>",
                        ),
                        status=404,
                    )
            except Exception as error:  # noqa: BLE001 — surface to caller, not stderr
                web_runner_logger.warning(f"dashboard handler error: {error!r}")
                self._send_json({"error": repr(error)}, status=500)

    return DashboardHandler


# ---------- server wrapper -----------------------------------------------

class DashboardServer:
    """
    包 ThreadingHTTPServer 的薄殼,start/stop/url。``start`` 不阻塞,
    所以可以從測試 / shell 直接用。
    """

    def __init__(self, config: Optional[DashboardConfig] = None) -> None:
        self.config = config or DashboardConfig()
        self._httpd: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._bound: Optional[Tuple[str, int]] = None

    def start(self) -> str:
        """Bind + spawn a daemon thread serving requests. Returns the URL."""
        if self._httpd is not None:
            raise LiveDashboardError("server already started")
        handler_cls = _make_handler(self.config)
        try:
            self._httpd = ThreadingHTTPServer(
                (self.config.bind_host, self.config.bind_port), handler_cls,
            )
        except OSError as error:
            raise LiveDashboardError(
                f"cannot bind {self.config.bind_host}:{self.config.bind_port}: {error!r}"
            ) from error
        self._bound = self._httpd.server_address
        self._thread = threading.Thread(
            target=self._httpd.serve_forever,
            name="webrunner-dashboard",
            daemon=True,
        )
        self._thread.start()
        web_runner_logger.info(f"dashboard listening on {self.url}")
        return self.url

    def stop(self, *, timeout: float = 5.0) -> None:
        """Shut down the server and join the thread."""
        if self._httpd is None:
            return
        try:
            self._httpd.shutdown()
            self._httpd.server_close()
        except OSError as error:
            web_runner_logger.warning(f"dashboard stop: {error!r}")
        if self._thread is not None:
            self._thread.join(timeout=timeout)
        self._httpd = None
        self._thread = None
        self._bound = None

    @property
    def url(self) -> str:
        if self._bound is None:
            raise LiveDashboardError("server not started")
        host, port = self._bound
        if host in {"0.0.0.0", "::"}:
            host = "127.0.0.1"
        return f"http://{host}:{port}"

    def __enter__(self) -> "DashboardServer":
        self.start()
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.stop()
