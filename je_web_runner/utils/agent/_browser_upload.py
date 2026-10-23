"""Upload only explicit bounded bytes to one owned file input and verify its metadata."""
from __future__ import annotations

import hashlib
from typing import Any

from je_web_runner.utils.agent.browser import BrowserSession
from je_web_runner.utils.agent.types import AgentError

MAX_UPLOAD = 4 * 1024 * 1024
_INPUT = "element => element.tagName === 'INPUT' && element.type === 'file'"
_FILES = "element => [...element.files].map(file => ({name: file.name, size: file.size}))"


def _filename(value: str) -> None:
    if not isinstance(value, str) or not value or len(value) > 255:
        raise AgentError("managed upload requires a plain bounded filename")
    if any(character in value for character in '/\\:\r\n\x00') or value in {".", ".."}:
        raise AgentError("managed upload filename is invalid")
    try:
        if len(value.encode("utf-16-le")) > 510:
            raise AgentError("managed upload filename is too long")
    except UnicodeError:
        raise AgentError("managed upload filename contains invalid Unicode") from None


def upload_bytes(session: BrowserSession, selector: str, contents: bytes, name: str, frame: str) -> dict[str, Any]:
    """Set one visible unique enabled file input; no path, picker, script or automatic submission is accepted."""
    _filename(name)
    if not isinstance(contents, bytes) or not 0 < len(contents) <= MAX_UPLOAD:
        raise AgentError("managed upload requires from one byte to four megabytes")
    with session.scope(frame) as scope:
        element = session._find(scope, selector, enabled=True)  # pylint: disable=protected-access
        if element.evaluate(_INPUT) is not True:
            raise AgentError("managed upload requires a file input")
        element.set_input_files({"name": name, "mimeType": "application/octet-stream", "buffer": contents})
        if element.evaluate(_FILES) != [{"name": name, "size": len(contents)}]:
            raise AgentError("managed upload readback does not match")
    return {"name": name, "bytes": len(contents), "sha256": hashlib.sha256(contents).hexdigest()}
