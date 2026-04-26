"""
Visual diff 本機審視 UI：side-by-side baseline / current，一鍵 accept。
Local visual-diff review server. Walks ``baseline_dir`` / ``current_dir``
for matching ``*.png`` files and renders an HTML page that places each
pair side-by-side. Clicking *Accept* copies the current PNG over the
baseline.

Designed to pair with :mod:`visual_regression` outputs.
"""
from __future__ import annotations

import html as _html
import shutil
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Callable, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class VisualReviewError(WebRunnerException):
    """Raised when accept / list operations fail."""


@dataclass
class _Pair:
    name: str
    baseline: Optional[Path]
    current: Optional[Path]
    status: str  # "match" | "diff" | "missing-baseline" | "missing-current"


def _pairs(baseline_dir: Path, current_dir: Path) -> List[_Pair]:
    baseline_files = {p.name: p for p in baseline_dir.glob("*.png")} if baseline_dir.is_dir() else {}
    current_files = {p.name: p for p in current_dir.glob("*.png")} if current_dir.is_dir() else {}
    names = sorted(set(baseline_files) | set(current_files))
    pairs: List[_Pair] = []
    for name in names:
        baseline = baseline_files.get(name)
        current = current_files.get(name)
        if baseline and current:
            same = baseline.read_bytes() == current.read_bytes()
            status = "match" if same else "diff"
        elif baseline is None:
            status = "missing-baseline"
        else:
            status = "missing-current"
        pairs.append(_Pair(name=name, baseline=baseline, current=current, status=status))
    return pairs


def list_diffs(baseline_dir: str, current_dir: str) -> List[Dict[str, str]]:
    """Return ``[{name, status}]`` for every paired snapshot."""
    pairs = _pairs(Path(baseline_dir), Path(current_dir))
    return [{"name": p.name, "status": p.status} for p in pairs]


def accept_baseline(baseline_dir: str, current_dir: str, name: str) -> Path:
    """
    Copy ``current_dir/name`` over ``baseline_dir/name`` (creating dir).
    """
    if not name or "/" in name or "\\" in name or name.startswith(".."):
        raise VisualReviewError(f"unsafe baseline name: {name!r}")
    current = Path(current_dir) / name
    baseline_target = Path(baseline_dir) / name
    if not current.is_file():
        raise VisualReviewError(f"current file missing: {current}")
    baseline_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(current, baseline_target)
    return baseline_target


_INDEX_HTML = """
<!doctype html>
<html><head><meta charset='utf-8'><title>WebRunner visual review</title>
<style>
  body{{font-family:-apple-system,Segoe UI,sans-serif;margin:1.5rem;}}
  table{{border-collapse:collapse;width:100%;}}
  th,td{{border:1px solid #ccc;padding:.4rem;vertical-align:top;}}
  img{{max-width:380px;display:block;}}
  .diff{{background:#fff7ed;}}
  .match{{background:#ecfdf5;}}
  .missing-baseline,.missing-current{{background:#fef2f2;}}
  form{{display:inline;}}
</style></head>
<body>
  <h1>Visual review</h1>
  <p>baseline: <code>{baseline}</code><br/>current: <code>{current}</code></p>
  <table>
    <thead><tr><th>Name</th><th>Status</th><th>Baseline</th><th>Current</th><th>Action</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</body></html>
"""


def _row_html(pair: _Pair) -> str:
    baseline_img = (
        f"<img src='/img/baseline/{_html.escape(pair.name)}' alt='baseline'/>"
        if pair.baseline else "<em>missing</em>"
    )
    current_img = (
        f"<img src='/img/current/{_html.escape(pair.name)}' alt='current'/>"
        if pair.current else "<em>missing</em>"
    )
    accept_btn = ""
    if pair.status in {"diff", "missing-baseline"} and pair.current is not None:
        accept_btn = (
            f"<form method='POST' action='/accept'>"
            f"<input type='hidden' name='name' value='{_html.escape(pair.name)}'/>"
            f"<button type='submit'>Accept current as baseline</button></form>"
        )
    return (
        f"<tr class='{pair.status}'>"
        f"<td>{_html.escape(pair.name)}</td>"
        f"<td>{pair.status}</td>"
        f"<td>{baseline_img}</td>"
        f"<td>{current_img}</td>"
        f"<td>{accept_btn}</td>"
        f"</tr>"
    )


def render_index(baseline_dir: str, current_dir: str) -> str:
    pairs = _pairs(Path(baseline_dir), Path(current_dir))
    rows = "".join(_row_html(p) for p in pairs) or "<tr><td colspan='5'><em>No snapshots</em></td></tr>"
    return _INDEX_HTML.format(
        baseline=_html.escape(str(Path(baseline_dir).resolve())),
        current=_html.escape(str(Path(current_dir).resolve())),
        rows=rows,
    )


class VisualReviewServer:
    """HTTP server that powers the review UI."""

    def __init__(
        self,
        baseline_dir: str,
        current_dir: str,
        host: str = "127.0.0.1",
        port: int = 0,
    ) -> None:
        self.baseline_dir = baseline_dir
        self.current_dir = current_dir
        self.host = host
        self.port = port
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self.accepted: List[str] = []

    def start(self) -> str:
        if self._server is not None:
            raise VisualReviewError("review server already started")
        handler = _make_handler(self)
        srv = HTTPServer((self.host, self.port), handler)
        thread = threading.Thread(target=srv.serve_forever, daemon=True)
        thread.start()
        self._server = srv
        self._thread = thread
        self.port = srv.server_address[1]
        web_runner_logger.info(
            f"visual_review listening on {self.host}:{self.port}"
        )
        return f"http://{self.host}:{self.port}"  # NOSONAR — local UI

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
            self._thread = None


_TEXT_PLAIN = "text/plain"


def _make_handler(server: VisualReviewServer) -> Callable:

    class _ReviewHandler(BaseHTTPRequestHandler):

        def log_message(self, format, *args):  # pylint: disable=redefined-builtin
            return

        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/" or parsed.path == "/index.html":
                self._send(
                    200,
                    render_index(server.baseline_dir, server.current_dir).encode("utf-8"),
                    "text/html; charset=utf-8",
                )
                return
            if parsed.path.startswith("/img/baseline/") or parsed.path.startswith("/img/current/"):
                bucket, _, name = parsed.path[5:].partition("/")  # strip "/img/"
                base = server.baseline_dir if bucket == "baseline" else server.current_dir
                target = (Path(base) / name).resolve()
                base_resolved = Path(base).resolve()
                try:
                    target.relative_to(base_resolved)
                except ValueError:
                    self._send(404, b"", _TEXT_PLAIN)
                    return
                if not target.is_file():
                    self._send(404, b"", _TEXT_PLAIN)
                    return
                self._send(200, target.read_bytes(), "image/png")
                return
            self._send(404, b"not found", _TEXT_PLAIN)

        def do_POST(self):  # noqa: N802
            if self.path != "/accept":
                self._send(404, b"not found", _TEXT_PLAIN)
                return
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length).decode("utf-8") if length else ""
            params = parse_qs(body)
            names = params.get("name") or []
            if not names:
                self._send(400, b"missing name", _TEXT_PLAIN)
                return
            try:
                accept_baseline(server.baseline_dir, server.current_dir, names[0])
            except VisualReviewError as error:
                self._send(400, str(error).encode("utf-8"), _TEXT_PLAIN)
                return
            server.accepted.append(names[0])
            self.send_response(303)
            self.send_header("Location", "/")
            self.end_headers()

    return _ReviewHandler
