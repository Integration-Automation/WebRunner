"""
Live Dashboard:把既有 run_ledger / flake_detector / locator_health /
failure_triage / test_scheduler / quarantine registry 的資料整合在一個
本地 web UI。

純 stdlib(``http.server``),不加新依賴。預設只 bind 127.0.0.1,
單 process,跟 socket_server 共存無干擾。

Routes:

* ``GET /``               overview: summary cards, daily pass-rate chart, latest runs
* ``GET /runs``           recent ledger entries (``?limit=N``, "Show more" adds 50)
* ``GET /flake``          flake leaderboard
* ``GET /quarantine``     quarantine registry, with triage links
* ``GET /locators``       locator health: cards, weakest locators, fallback offenders
* ``GET /schedule``       test-scheduler plan: selected and skipped tests
* ``GET /triage``         failure-triage report(s)
* ``GET /api/summary``    JSON aggregate counts
* ``GET /api/runs``       JSON recent runs (``?limit=N``)
* ``GET /api/flake``      JSON flake scores
* ``GET /api/quarantine`` JSON quarantine entries
* ``GET /api/locators``   JSON locator findings
* ``GET /api/schedule``   JSON schedule report, passed through
* ``GET /api/triage``     JSON triage report, passed through
* ``GET /api/trend``      JSON per-day pass / fail counts
* ``GET /static/app.css``, ``/static/app.js``, ``/static/favicon.svg``: same-origin
  assets, because the pages' CSP (``default-src 'self'``) blocks inline ones
* ``GET /healthz``        ``ok``

The pages work without JavaScript; the script adds local times, sortable and
filterable tables and a refresh every 15 seconds (with a pause button).
Every request re-reads the underlying files so the dashboard always
reflects the latest state — no caching, no daemon process needed.
"""
from __future__ import annotations

import json
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable

from je_web_runner.utils.live_dashboard._assets import FAVICON, SCRIPT, STYLESHEET
from je_web_runner.utils.live_dashboard._config import DashboardConfig, LiveDashboardError
from je_web_runner.utils.live_dashboard._data import (
    _load_flake_scores,
    _load_locator_report,
    _load_quarantine,
    _load_runs,
    _load_schedule,
    _load_triage,
    build_summary,
    load_overview,
    load_runs_page,
    load_trend,
)
from je_web_runner.utils.live_dashboard._pages import (
    render_flake,
    render_locators,
    render_not_found,
    render_overview,
    render_quarantine,
    render_runs,
    render_schedule,
    render_triage,
)
from je_web_runner.utils.logging.loggin_instance import web_runner_logger

__all__ = ["DashboardConfig", "DashboardServer", "LiveDashboardError", "build_summary"]


def _make_handler(config: DashboardConfig) -> type[BaseHTTPRequestHandler]:
    """Bind ``config`` into a fresh handler class so each server is isolated."""

    html_routes: dict[str, Callable[[str], str]] = {
        "/": lambda _query: render_overview(**load_overview(config)),
        "/runs": lambda query: _runs_page(config, _query_limit(query)),
        "/flake": lambda _query: render_flake(_load_flake_scores(config.ledger_path)),
        "/quarantine": lambda _query: render_quarantine(_load_quarantine(config.quarantine_path)),
        "/locators": lambda _query: render_locators(_load_locator_report(config.locator_findings_path)),
        "/schedule": lambda _query: render_schedule(_load_schedule(config.schedule_path)),
        "/triage": lambda _query: render_triage(_load_triage(config.triage_report_path)),
    }
    json_routes: dict[str, Callable[[Any], Any]] = {
        "/api/summary": lambda _query: build_summary(config),
        "/api/runs": lambda query: _load_runs(config.ledger_path, _query_limit(query)),
        "/api/flake": lambda _query: _load_flake_scores(config.ledger_path),
        "/api/quarantine": lambda _query: _load_quarantine(config.quarantine_path),
        "/api/locators": lambda _query: _load_locator_report(config.locator_findings_path),
        "/api/schedule": lambda _query: _load_schedule(config.schedule_path),
        "/api/triage": lambda _query: _load_triage(config.triage_report_path),
        "/api/trend": lambda _query: load_trend(config.ledger_path),
    }
    text_routes: dict[str, tuple[str, bytes]] = {
        "/static/app.css": ("text/css; charset=utf-8", STYLESHEET.encode("utf-8")),
        "/static/app.js": ("text/javascript; charset=utf-8", SCRIPT.encode("utf-8")),
        "/static/favicon.svg": ("image/svg+xml", FAVICON.encode("utf-8")),
        "/healthz": ("text/plain", b"ok"),
    }

    class DashboardHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format: str, *args: Any) -> None:  # pylint: disable=redefined-builtin — match BaseHTTPRequestHandler signature
            web_runner_logger.info(f"dashboard: {format % args}")

        def _send(self, status: int, content_type: str, body: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'")
            self.end_headers()
            # Body callers escape any user-controlled text via html_escape before
            # reaching here (see _send_html). The CSP + nosniff headers above are
            # defence in depth.
            # NOSONAR below: pages escape every value via html_escape; CSP + nosniff are defence in depth.
            self.wfile.write(body)  # NOSONAR pythonsecurity:S5131

        def _send_html(self, page: str, status: int = 200) -> None:
            self._send(status, "text/html; charset=utf-8", page.encode("utf-8"))

        def _send_json(self, payload: Any, status: int = 200) -> None:
            body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            self._send(status, "application/json; charset=utf-8", body)

        def do_GET(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            try:
                if path in html_routes:
                    self._send_html(html_routes[path](parsed.query))
                elif path in json_routes:
                    self._send_json(json_routes[path](parsed.query))
                elif path in text_routes:
                    self._send(200, *text_routes[path])
                else:
                    self._send_html(render_not_found(path), status=404)
            except Exception as error:  # NOSONAR python:S5754 — a 500, not a dead worker thread
                web_runner_logger.warning(f"dashboard handler error: {error!r}")
                self._send_json({"error": repr(error)}, status=500)

    return DashboardHandler


def _runs_page(config: DashboardConfig, limit: int) -> str:
    runs, total = load_runs_page(config.ledger_path, limit)
    return render_runs(runs, total, limit)


def _query_limit(query: str) -> int:
    params = urllib.parse.parse_qs(query)
    raw = params.get("limit", ["50"])[0]
    try:
        value = int(raw)
    except ValueError:
        value = 50
    return max(1, min(value, 5000))


# ---------- server wrapper -----------------------------------------------

class DashboardServer:
    """
    包 ThreadingHTTPServer 的薄殼,start/stop/url。``start`` 不阻塞,
    所以可以從測試 / shell 直接用。
    """

    def __init__(self, config: DashboardConfig | None = None) -> None:
        self.config = config or DashboardConfig()
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._bound: tuple[str, int] | None = None

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
        if host in {"0.0.0.0", "::"}:  # nosec B104 — string compare detecting "bind all"; rewritten to 127.0.0.1 in the URL below
            host = "127.0.0.1"
        # S5332 ok: dashboard binds to loopback by default; intentionally HTTP
        # so the user can open it in a browser without a self-signed cert.
        return f"http://{host}:{port}"  # NOSONAR S5332 — plain HTTP on purpose: a localhost dev endpoint

    def __enter__(self) -> DashboardServer:
        self.start()
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.stop()
