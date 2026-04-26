"""
自動產生 ``WR_*`` 命令參考（Markdown）。
Auto-generate a Markdown reference for every registered ``WR_*`` command
by introspecting the executor's ``event_dict``: name → signature → first
line of the callable's docstring.
"""
from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any, Callable, List, Optional, Tuple

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class DocsExportError(WebRunnerException):
    """Raised when a documentation file cannot be written."""


def _signature_for(callable_obj: Any) -> str:
    try:
        return str(inspect.signature(callable_obj))
    except (TypeError, ValueError):
        return "(...)"


def _first_doc_line(callable_obj: Any) -> str:
    raw = inspect.getdoc(callable_obj) or ""
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def _command_entries() -> List[Tuple[str, Callable[..., Any]]]:
    """Return every ``WR_*`` entry from the executor in sorted order."""
    from je_web_runner.utils.executor.action_executor import executor
    return sorted(
        ((name, fn) for name, fn in executor.event_dict.items() if name.startswith("WR_")),
        key=lambda pair: pair[0].lower(),
    )


def build_command_reference(title: str = "WebRunner command reference") -> str:
    """
    產生整份命令參考（Markdown 字串）
    Build the full Markdown reference as one string.
    """
    web_runner_logger.info("build_command_reference")
    entries = _command_entries()
    lines: List[str] = [
        f"# {title}",
        "",
        f"Auto-generated from the executor's event_dict ({len(entries)} commands).",
        "",
        "| Command | Signature | Summary |",
        "| --- | --- | --- |",
    ]
    for name, fn in entries:
        signature = _signature_for(fn)
        summary = _first_doc_line(fn).replace("|", "\\|")
        lines.append(f"| `{name}` | `{signature}` | {summary} |")
    return "\n".join(lines) + "\n"


def export_command_reference(path: str, title: Optional[str] = None) -> str:
    """Write the Markdown reference to ``path`` and return the resolved path."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    body = build_command_reference(title or "WebRunner command reference")
    try:
        target.write_text(body, encoding="utf-8")
    except OSError as error:
        raise DocsExportError(f"failed to write reference: {error}") from error
    return str(target.resolve())


def list_commands() -> List[str]:
    """Just the command names (handy for shell completion)."""
    return [name for name, _ in _command_entries()]
