"""
失敗時打包重現用素材：screenshot / DOM snapshot / 網路紀錄 / console / trace。
Failure bundle: collect screenshot bytes, DOM HTML, network log, console
log, OTel trace, and any extra files into a single zip with a manifest.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from je_web_runner.utils.exception.exceptions import WebRunnerException


class FailureBundleError(WebRunnerException):
    """Raised when bundle building or reading fails."""


_MANIFEST_NAME = "manifest.json"


def _utc_now_iso() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).isoformat(timespec="seconds")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass
class FailureBundle:
    """Builder for one failure bundle."""

    test_name: str
    error_repr: str
    captured_at: str = field(default_factory=_utc_now_iso)
    metadata: Dict[str, Any] = field(default_factory=dict)
    _entries: Dict[str, bytes] = field(default_factory=dict)

    def add_screenshot(self, png_bytes: bytes, name: str = "screenshot.png") -> None:
        if not isinstance(png_bytes, (bytes, bytearray)):
            raise FailureBundleError("screenshot must be bytes")
        self._entries[f"artifacts/{name}"] = bytes(png_bytes)

    def add_dom(self, html: str, name: str = "dom.html") -> None:
        self._entries[f"artifacts/{name}"] = html.encode("utf-8")

    def add_console(self, messages: List[Dict[str, Any]]) -> None:
        self._entries["artifacts/console.json"] = json.dumps(
            messages, ensure_ascii=False, indent=2
        ).encode("utf-8")

    def add_network(self, responses: List[Dict[str, Any]]) -> None:
        self._entries["artifacts/network.json"] = json.dumps(
            responses, ensure_ascii=False, indent=2
        ).encode("utf-8")

    def add_trace(self, trace_path: Union[str, Path]) -> None:
        path = Path(trace_path)
        if not path.is_file():
            raise FailureBundleError(f"trace file not found: {trace_path!r}")
        self._entries[f"artifacts/{path.name}"] = path.read_bytes()

    def add_file(self, source: Union[str, Path], inside_name: Optional[str] = None) -> None:
        path = Path(source)
        if not path.is_file():
            raise FailureBundleError(f"file not found: {source!r}")
        target = inside_name or f"artifacts/{path.name}"
        self._entries[target] = path.read_bytes()

    def add_text(self, name: str, text: str) -> None:
        self._entries[f"artifacts/{name}"] = text.encode("utf-8")

    def _manifest(self) -> Dict[str, Any]:
        return {
            "test_name": self.test_name,
            "error_repr": self.error_repr,
            "captured_at": self.captured_at,
            "metadata": self.metadata,
            "artifacts": [
                {"name": name, "size": len(data), "sha256": _sha256_bytes(data)}
                for name, data in sorted(self._entries.items())
            ],
        }

    def write(self, output_path: Union[str, Path]) -> Path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(
                _MANIFEST_NAME,
                json.dumps(self._manifest(), ensure_ascii=False, indent=2),
            )
            for name, data in sorted(self._entries.items()):
                zf.writestr(name, data)
        return path


def extract_bundle(zip_path: Union[str, Path]) -> Dict[str, Any]:
    """Read a bundle and return ``{manifest, files: {name: bytes}}``."""
    path = Path(zip_path)
    if not path.is_file():
        raise FailureBundleError(f"bundle not found: {zip_path!r}")
    files: Dict[str, bytes] = {}
    with zipfile.ZipFile(path, "r") as zf:
        names = zf.namelist()
        if _MANIFEST_NAME not in names:
            raise FailureBundleError("manifest.json missing from bundle")
        manifest = json.loads(zf.read(_MANIFEST_NAME).decode("utf-8"))
        for name in names:
            if name == _MANIFEST_NAME:
                continue
            files[name] = zf.read(name)
    return {"manifest": manifest, "files": files}
