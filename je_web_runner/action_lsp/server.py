"""
Action JSON LSP server：基於 LSP 3.17 protocol，提供 ``WR_*`` 補全與 lint 診斷。
Minimal LSP server speaking JSON-RPC 2.0 over stdio with the standard
``Content-Length`` headers. Supports:

- ``initialize`` / ``initialized`` / ``shutdown`` / ``exit``
- ``textDocument/didOpen`` / ``didChange`` / ``didClose``
- ``textDocument/completion`` — suggests every registered ``WR_*`` command
- ``textDocument/publishDiagnostics`` — pushes lint findings on document
  open / change

The action linter and command list are pulled from existing modules so
the LSP stays a thin presentation layer.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TextIO

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class ActionLspError(WebRunnerException):
    """Raised when a request can't be parsed or handled."""


@dataclass
class _Document:
    uri: str
    text: str
    version: int = 0


@dataclass
class ActionLspServer:
    documents: Dict[str, _Document] = field(default_factory=dict)
    initialized: bool = False
    _command_names: Optional[List[str]] = field(default=None, init=False, repr=False)

    def command_names(self) -> List[str]:
        if self._command_names is None:
            try:
                from je_web_runner.utils.executor.action_executor import executor
                names = sorted(executor.event_dict.keys())
            except Exception as error:  # pylint: disable=broad-except
                web_runner_logger.warning(f"action_lsp executor unavailable: {error!r}")
                names = []
            self._command_names = [n for n in names if isinstance(n, str)]
        return self._command_names

    # --- Top-level dispatch ----------------------------------------------

    def handle(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        method = message.get("method")
        request_id = message.get("id")
        params = message.get("params") or {}
        if method == "initialize":
            return self._respond(request_id, self._initialize())
        if method == "initialized":
            self.initialized = True
            return None
        if method == "shutdown":
            return self._respond(request_id, None)
        if method == "exit":
            return None
        if method == "textDocument/didOpen":
            return self._on_did_open(params)
        if method == "textDocument/didChange":
            return self._on_did_change(params)
        if method == "textDocument/didClose":
            return self._on_did_close(params)
        if method == "textDocument/completion":
            return self._respond(request_id, self._completion(params))
        return self._error(request_id, -32601, f"unknown method {method!r}")

    # --- Handlers --------------------------------------------------------

    def _initialize(self) -> Dict[str, Any]:
        return {
            "capabilities": {
                "textDocumentSync": 1,  # full sync
                "completionProvider": {"triggerCharacters": ['"', "_"]},
            },
            "serverInfo": {"name": "webrunner-action-lsp", "version": "0.1.0"},
        }

    def _on_did_open(self, params: Dict[str, Any]) -> Dict[str, Any]:
        document = params.get("textDocument") or {}
        uri = str(document.get("uri", ""))
        text = str(document.get("text", ""))
        self.documents[uri] = _Document(uri=uri, text=text, version=int(document.get("version", 0)))
        return self._diagnostics_notification(uri, text)

    def _on_did_change(self, params: Dict[str, Any]) -> Dict[str, Any]:
        document = params.get("textDocument") or {}
        uri = str(document.get("uri", ""))
        changes = params.get("contentChanges") or []
        if uri not in self.documents:
            return self._diagnostics_notification(uri, "")
        full_text = self.documents[uri].text
        for change in changes:
            if isinstance(change, dict) and "text" in change:
                full_text = str(change["text"])
        self.documents[uri].text = full_text
        self.documents[uri].version = int(document.get("version", 0))
        return self._diagnostics_notification(uri, full_text)

    def _on_did_close(self, params: Dict[str, Any]) -> None:
        uri = str((params.get("textDocument") or {}).get("uri", ""))
        self.documents.pop(uri, None)
        return None

    def _completion(self, params: Dict[str, Any]) -> Dict[str, Any]:
        items = [
            {
                "label": name,
                "kind": 14,  # CompletionItemKind.Keyword
                "detail": "WebRunner action command",
                "insertText": name,
            }
            for name in self.command_names()
        ]
        return {"isIncomplete": False, "items": items}

    # --- Diagnostics -----------------------------------------------------

    def _diagnostics_notification(self, uri: str, text: str) -> Dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "method": "textDocument/publishDiagnostics",
            "params": {
                "uri": uri,
                "diagnostics": self._lint_diagnostics(text),
            },
        }

    def _lint_diagnostics(self, text: str) -> List[Dict[str, Any]]:
        if not text.strip():
            return []
        try:
            actions = json.loads(text)
        except ValueError as error:
            return [_diagnostic(error_message=f"JSON parse error: {error}",
                                line=0, severity=1)]
        if not isinstance(actions, list):
            return [_diagnostic("Action document root must be a JSON array.",
                                line=0, severity=1)]
        diagnostics: List[Dict[str, Any]] = []
        try:
            from je_web_runner.utils.linter.action_linter import lint_action
        except Exception:  # pylint: disable=broad-except
            return diagnostics
        for finding in lint_action(actions):
            severity = 1 if finding.level == "error" else 2
            diagnostics.append(_diagnostic(
                error_message=f"[{finding.rule}] {finding.message}",
                line=finding.index,
                severity=severity,
            ))
        return diagnostics

    # --- Helpers ---------------------------------------------------------

    @staticmethod
    def _respond(request_id: Any, result: Any) -> Dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    @staticmethod
    def _error(request_id: Any, code: int, message: str) -> Dict[str, Any]:
        return {
            "jsonrpc": "2.0", "id": request_id,
            "error": {"code": code, "message": message},
        }


def _diagnostic(error_message: str, line: int, severity: int) -> Dict[str, Any]:
    return {
        "range": {
            "start": {"line": max(0, line), "character": 0},
            "end": {"line": max(0, line), "character": 200},
        },
        "severity": severity,
        "source": "webrunner-action-lsp",
        "message": error_message,
    }


# --- LSP framing -----------------------------------------------------------

_HEADER_TERMINATOR = "\r\n\r\n"


def _read_message(stdin: TextIO) -> Optional[Dict[str, Any]]:
    headers: Dict[str, str] = {}
    while True:
        line = stdin.readline()
        if line == "":
            return None
        line = line.rstrip("\r\n")
        if not line:
            break
        if ":" in line:
            name, _, value = line.partition(":")
            headers[name.strip().lower()] = value.strip()
    length_str = headers.get("content-length")
    if length_str is None:
        return None
    try:
        length = int(length_str)
    except ValueError as error:
        raise ActionLspError(f"invalid Content-Length: {error}") from error
    body = stdin.read(length)
    if not body:
        return None
    try:
        return json.loads(body)
    except ValueError as error:
        raise ActionLspError(f"body is not JSON: {error}") from error


def _write_message(stdout: TextIO, message: Dict[str, Any]) -> None:
    body = json.dumps(message, ensure_ascii=False)
    stdout.write(f"Content-Length: {len(body.encode('utf-8'))}\r\n\r\n{body}")
    stdout.flush()


def serve_stdio(
    stdin: Optional[TextIO] = None,
    stdout: Optional[TextIO] = None,
    server: Optional[ActionLspServer] = None,
) -> None:
    """Run the LSP loop until stdin EOF or an ``exit`` notification."""
    in_stream = stdin or sys.stdin
    out_stream = stdout or sys.stdout
    used_server = server or ActionLspServer()
    while True:
        try:
            message = _read_message(in_stream)
        except ActionLspError as error:
            web_runner_logger.warning(f"action_lsp parse error: {error}")
            continue
        if message is None:
            return
        response = used_server.handle(message)
        if message.get("method") == "exit":
            return
        if response is not None:
            _write_message(out_stream, response)
