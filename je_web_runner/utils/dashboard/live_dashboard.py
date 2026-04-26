"""
即時 progress dashboard：簡單 HTTP server，瀏覽器可直接看到執行進度。
Tiny HTTP server that exposes the current ``test_record_instance`` snapshot
so a browser dashboard can poll and render live progress without external
tooling.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.utils.test_record.test_record_class import test_record_instance


class DashboardError(WebRunnerException):
    """Raised when the dashboard cannot be started."""


_INDEX_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>WebRunner live</title>
<style>body{font-family:sans-serif;margin:1rem}
table{border-collapse:collapse;width:100%}
th,td{border:1px solid #ddd;padding:4px 8px;font-size:13px;text-align:left}
.fail td{background:#fff4f4}.ok td{background:#fafffa}</style>
</head><body>
<h1>WebRunner live</h1>
<p id="summary">loading…</p>
<table id="tbl"><thead><tr>
<th>#</th><th>Time</th><th>Action</th><th>Status</th><th>Exception</th>
</tr></thead><tbody id="rows"></tbody></table>
<script>
async function refresh(){
  try{
    const res = await fetch('/records');
    const data = await res.json();
    document.getElementById('summary').textContent =
      `total=${data.total}  passed=${data.passed}  failed=${data.failed}`;
    const rows = document.getElementById('rows');
    rows.innerHTML = '';
    data.records.forEach((r, i) => {
      const tr = document.createElement('tr');
      tr.className = r.status === 'failed' ? 'fail' : 'ok';
      tr.innerHTML = `<td>${i+1}</td><td>${r.time||''}</td>
        <td>${r.function_name||''}</td><td>${r.status}</td>
        <td>${r.exception||''}</td>`;
      rows.appendChild(tr);
    });
  } catch (e) { /* ignore — keep polling */ }
}
setInterval(refresh, 1000);
refresh();
</script></body></html>
"""


def _records_payload() -> dict:
    records = []
    failed = 0
    for record in test_record_instance.test_record_list:
        exception = record.get("program_exception", "None")
        status = "failed" if exception != "None" else "passed"
        if status == "failed":
            failed += 1
        records.append({
            "function_name": record.get("function_name"),
            "time": record.get("time"),
            "status": status,
            "exception": exception if status == "failed" else "",
        })
    total = len(records)
    return {"total": total, "passed": total - failed, "failed": failed, "records": records}


class _Handler(BaseHTTPRequestHandler):

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802 — http.server convention
        if self.path == "/" or self.path == "/index.html":
            self._send(200, _INDEX_HTML.encode("utf-8"), "text/html; charset=utf-8")
            return
        if self.path == "/records":
            payload = json.dumps(_records_payload()).encode("utf-8")
            self._send(200, payload, "application/json")
            return
        self._send(404, b"not found", "text/plain")

    def log_message(self, format: str, *args: Any) -> None:  # pylint: disable=redefined-builtin
        # ``format`` shadows the built-in here because BaseHTTPRequestHandler
        # defines the method with that exact parameter name; renaming would
        # break the override contract. Routes through WebRunner's logger.
        web_runner_logger.debug("dashboard: " + (format % args))


class LiveDashboard:
    """Threaded HTTP server exposing /records for a polling browser page."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0) -> None:
        self._host = host
        self._port = int(port)
        self._server: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    @property
    def address(self) -> str:
        if self._server is None:
            raise DashboardError("dashboard is not running")
        host, port = self._server.server_address
        # Local-only progress dashboard, served over plain HTTP by design;
        # SonarCloud S5332 is a false positive on this URL builder.
        return f"http://{host}:{port}"  # NOSONAR

    def start(self) -> str:
        web_runner_logger.info(f"LiveDashboard.start {self._host}:{self._port}")
        self._server = ThreadingHTTPServer((self._host, self._port), _Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self.address

    def stop(self) -> None:
        if self._server is None:
            return
        self._server.shutdown()
        self._server.server_close()
        self._server = None
        self._thread = None


_default = LiveDashboard()


def start_dashboard(host: str = "127.0.0.1", port: int = 0) -> str:
    _default._host = host
    _default._port = int(port)
    return _default.start()


def stop_dashboard() -> None:
    _default.stop()
