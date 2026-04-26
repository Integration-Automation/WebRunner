"""
HAR replay server：把 har_diff 收到的 HAR 反過來當 mock backend。
HAR replay server. Loads a HAR file and serves matching responses for
incoming requests so e2e tests can run completely offline.

Matching is keyed on ``(method, url-path-with-query)``; if the same key
appears multiple times in the HAR, replay rotates through them in order
and stays on the last entry once exhausted.
"""
from __future__ import annotations

import json
import re
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from urllib.parse import urlparse

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class HarReplayError(WebRunnerException):
    """Raised when the HAR file is invalid or the server can't bind."""


@dataclass
class HarEntry:
    method: str
    path: str
    status: int
    headers: Dict[str, str] = field(default_factory=dict)
    body: str = ""
    body_is_base64: bool = False


def load_har(source: Union[str, Path]) -> List[HarEntry]:
    """Read a HAR file and return its ``entries`` projected to :class:`HarEntry`."""
    path = Path(source)
    if not path.is_file():
        raise HarReplayError(f"HAR file not found: {source!r}")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as error:
        raise HarReplayError(f"HAR is not JSON: {error}") from error
    entries = (document.get("log") or {}).get("entries")
    if not isinstance(entries, list):
        raise HarReplayError("HAR missing log.entries")
    parsed: List[HarEntry] = []
    for index, entry in enumerate(entries):
        try:
            parsed.append(_entry_from_har(entry))
        except (KeyError, TypeError, ValueError) as error:
            web_runner_logger.warning(f"har_replay skipping entry {index}: {error}")
    return parsed


def _entry_from_har(entry: Dict[str, Any]) -> HarEntry:
    request = entry["request"]
    response = entry["response"]
    parsed = urlparse(request["url"])
    request_path = parsed.path or "/"
    if parsed.query:
        request_path = f"{request_path}?{parsed.query}"
    content = response.get("content") or {}
    headers = {
        h.get("name", ""): h.get("value", "")
        for h in response.get("headers") or []
        if isinstance(h, dict)
    }
    if content.get("mimeType"):
        headers.setdefault("content-type", content["mimeType"])
    return HarEntry(
        method=str(request.get("method", "GET")).upper(),
        path=request_path,
        status=int(response.get("status", 200)),
        headers=headers,
        body=str(content.get("text") or ""),
        body_is_base64=str(content.get("encoding", "")).lower() == "base64",
    )


_PathMatcher = Callable[[str], bool]


def _build_matcher(pattern: str) -> _PathMatcher:
    if pattern.startswith("re:"):
        regex = re.compile(pattern[3:])
        return lambda path: regex.search(path) is not None
    if "*" in pattern:
        regex = re.compile("^" + re.escape(pattern).replace(r"\*", ".*") + "$")
        return lambda path: regex.match(path) is not None
    return lambda path: path == pattern


@dataclass
class _Bucket:
    matcher: _PathMatcher
    pattern: str
    entries: List[HarEntry]
    cursor: int = 0


class HarReplayServer:
    """In-process HTTP server that replays HAR responses."""

    def __init__(
        self,
        entries: List[HarEntry],
        host: str = "127.0.0.1",
        port: int = 0,
        not_found_status: int = 404,
    ) -> None:
        if not entries:
            raise HarReplayError("entries must be non-empty")
        self.entries = entries
        self.host = host
        self.port = port
        self.not_found_status = not_found_status
        self._buckets: Dict[str, List[_Bucket]] = defaultdict(list)
        self._build_buckets()
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self.calls: List[Tuple[str, str]] = []

    def _build_buckets(self) -> None:
        grouped: Dict[Tuple[str, str], List[HarEntry]] = defaultdict(list)
        for entry in self.entries:
            grouped[(entry.method, entry.path)].append(entry)
        for (method, path), group in grouped.items():
            bucket = _Bucket(
                matcher=_build_matcher(path),
                pattern=path,
                entries=group,
            )
            self._buckets[method].append(bucket)

    def find(self, method: str, path: str) -> Optional[HarEntry]:
        method_upper = method.upper()
        self.calls.append((method_upper, path))
        candidates = self._buckets.get(method_upper) or []
        for bucket in candidates:
            if bucket.matcher(path):
                entry = bucket.entries[bucket.cursor]
                if bucket.cursor + 1 < len(bucket.entries):
                    bucket.cursor += 1
                return entry
        return None

    def start(self) -> str:
        if self._server is not None:
            raise HarReplayError("HAR replay server already started")
        handler = _make_handler(self)
        srv = HTTPServer((self.host, self.port), handler)
        thread = threading.Thread(target=srv.serve_forever, daemon=True)
        thread.start()
        self._server = srv
        self._thread = thread
        self.port = srv.server_address[1]
        web_runner_logger.info(f"har_replay listening on {self.host}:{self.port}")
        return f"http://{self.host}:{self.port}"  # NOSONAR — local mock

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
            self._thread = None


def _make_handler(server: HarReplayServer) -> Callable:

    class _ReplayHandler(BaseHTTPRequestHandler):

        def log_message(self, format, *args):  # pylint: disable=redefined-builtin
            return

        def _drain_body(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            if length:
                self.rfile.read(length)  # drain body; not used for matching

        def _serve(self) -> None:
            method = self.command
            request_path = self.path
            entry = server.find(method, request_path)
            if entry is None:
                # Sanitise the echoed fragments to ASCII allow-list characters
                # so any HTML / control bytes a malicious client embeds in the
                # path can't reach the response payload (defence in depth on
                # top of the JSON envelope + nosniff header).
                payload = json.dumps({
                    "error": "no har match",
                    "method": _safe_echo(method),
                    "path": _safe_echo(request_path),
                }).encode("utf-8")
                self.send_response(server.not_found_status)
                self.send_header("Content-Type", "application/json")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                # _safe_echo above strips control + HTML-special bytes; this
                # writes a JSON envelope with nosniff so reflected fragments
                # can't be sniffed as HTML by the browser.
                self.wfile.write(payload)  # NOSONAR S5131 — payload sanitised + JSON + nosniff
                return
            body_bytes = _entry_body_bytes(entry)
            self.send_response(entry.status)
            for name, value in entry.headers.items():
                if name.lower() not in {"content-length", "transfer-encoding"}:
                    self.send_header(name, value)
            self.send_header("Content-Length", str(len(body_bytes)))
            self.end_headers()
            self.wfile.write(body_bytes)

        def do_GET(self):  # noqa: N802
            self._serve()

        def do_DELETE(self):  # noqa: N802
            self._serve()

        def do_POST(self):  # noqa: N802
            self._drain_body()
            self._serve()

        # do_PUT and do_PATCH share POST's body-drain semantics; alias to
        # avoid SonarCloud S4144 duplicate-method-body findings.
        do_PUT = do_POST  # noqa: N815
        do_PATCH = do_POST  # noqa: N815

    return _ReplayHandler


def _entry_body_bytes(entry: HarEntry) -> bytes:
    if entry.body_is_base64:
        import base64
        try:
            return base64.b64decode(entry.body or "")
        except (ValueError, TypeError):
            return (entry.body or "").encode("utf-8")
    return (entry.body or "").encode("utf-8")


_ECHO_SAFE_CHARS = set(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789-._~:/?#[]@!$&'()*+,;=% "
)


def _safe_echo(text: str, limit: int = 200) -> str:
    """Strip characters outside the unreserved + pchar URI grammar.

    Used in the no-match 404 payload so a malicious request method or
    path can't smuggle HTML / control bytes into the response.
    """
    if not isinstance(text, str):
        return ""
    return "".join(ch for ch in text if ch in _ECHO_SAFE_CHARS)[:limit]
