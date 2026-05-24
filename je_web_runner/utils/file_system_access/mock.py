"""
模擬 File System Access API:``showOpenFilePicker`` / ``showSaveFilePicker``。
這些 API 預設會跳系統檔案對話框 → 在無頭瀏覽器 / Selenium 環境基本沒救。
此模組產生 JS shim,把對話框替換成「直接給定的 fake file handle」,並
記錄 app 後續寫入了什麼,讓測試斷言「點了 Save 之後寫入內容是 X」。
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class FileSystemAccessError(WebRunnerException):
    """Raised on bad mock-file definitions or harvest payload."""


# ---------- model -------------------------------------------------------

@dataclass(frozen=True)
class MockFile:
    """One pre-populated file the picker should return."""

    name: str
    contents: str = ""
    mime_type: str = "text/plain"

    def __post_init__(self) -> None:
        if not self.name or not isinstance(self.name, str):
            raise FileSystemAccessError("MockFile.name must be non-empty string")
        if not isinstance(self.contents, str):
            raise FileSystemAccessError("MockFile.contents must be a string")


@dataclass
class WriteEvent:
    """One write the app performed against a mocked save handle."""

    file_name: str
    sequence: int
    data: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------- script generation -------------------------------------------

_TEMPLATE = """
(function() {
  if (window.__wr_fsa_installed__) return;
  window.__wr_fsa_installed__ = true;
  window.__wr_fsa_writes__ = [];
  const openFiles = %(open_files)s;
  const saveName = %(save_name)s;
  let writeSeq = 0;

  function makeFile(spec) {
    const blob = new Blob([spec.contents], {type: spec.mime_type});
    return new File([blob], spec.name, {type: spec.mime_type});
  }

  function makeReadHandle(spec) {
    return {
      kind: 'file',
      name: spec.name,
      getFile: async function() { return makeFile(spec); }
    };
  }

  function makeWriteHandle(name) {
    return {
      kind: 'file',
      name: name,
      createWritable: async function() {
        return {
          write: async function(chunk) {
            const text = typeof chunk === 'string'
              ? chunk
              : (chunk && chunk.data) ? String(chunk.data) : '';
            writeSeq += 1;
            window.__wr_fsa_writes__.push({
              file_name: name, sequence: writeSeq, data: text
            });
          },
          truncate: async function() {},
          close: async function() {}
        };
      },
      getFile: async function() {
        return new File([''], name, {type: 'application/octet-stream'});
      }
    };
  }

  window.showOpenFilePicker = async function() {
    return openFiles.map(makeReadHandle);
  };
  window.showSaveFilePicker = async function(opts) {
    const finalName = (opts && opts.suggestedName) || saveName || 'untitled.txt';
    return makeWriteHandle(finalName);
  };
  window.showDirectoryPicker = async function() {
    return {
      kind: 'directory', name: 'mocked',
      values: async function*() {
        for (const spec of openFiles) yield makeReadHandle(spec);
      }
    };
  };
})();
""".strip()


def build_install_script(
    open_files: Sequence[MockFile] = (),
    *,
    save_suggested_name: Optional[str] = None,
) -> str:
    """Render the JS shim. Inject once per page via init-script."""
    files_payload = [
        {"name": f.name, "contents": f.contents, "mime_type": f.mime_type}
        for f in open_files
    ]
    return _TEMPLATE % {
        "open_files": json.dumps(files_payload),
        "save_name": json.dumps(save_suggested_name) if save_suggested_name else "null",
    }


HARVEST_SCRIPT = "return window.__wr_fsa_writes__ || [];"


# ---------- harvest -----------------------------------------------------

def parse_writes(payload: Any) -> List[WriteEvent]:
    """Convert the harvested array into typed :class:`WriteEvent` records."""
    if not isinstance(payload, list):
        raise FileSystemAccessError(
            f"writes payload must be list, got {type(payload).__name__}"
        )
    out: List[WriteEvent] = []
    for raw in payload:
        if not isinstance(raw, dict):
            continue
        try:
            out.append(WriteEvent(
                file_name=str(raw["file_name"]),
                sequence=int(raw["sequence"]),
                data=str(raw.get("data") or ""),
            ))
        except (KeyError, TypeError, ValueError) as error:
            raise FileSystemAccessError(
                f"malformed write entry {raw!r}: {error}"
            ) from error
    return out


# ---------- assertions --------------------------------------------------

def assert_no_writes(writes: Sequence[WriteEvent]) -> None:
    """Assert the app did not write anything."""
    if writes:
        first = writes[0]
        raise FileSystemAccessError(
            f"unexpected write to {first.file_name!r}: {first.data[:80]!r}"
        )


def assert_wrote(
    writes: Sequence[WriteEvent],
    *,
    file_name: Optional[str] = None,
    contains: Optional[str] = None,
) -> WriteEvent:
    """Assert at least one write matches name and/or substring."""
    if file_name is None and contains is None:
        raise FileSystemAccessError(
            "provide at least one of file_name / contains"
        )
    for write in writes:
        if file_name is not None and write.file_name != file_name:
            continue
        if contains is not None and contains not in write.data:
            continue
        return write
    raise FileSystemAccessError(
        f"no write matched file_name={file_name!r} contains={contains!r} "
        f"({len(writes)} writes seen)"
    )


def combined_payload(
    writes: Sequence[WriteEvent], file_name: str,
) -> str:
    """Concatenate every write for one file in sequence order."""
    if not isinstance(file_name, str) or not file_name:
        raise FileSystemAccessError("file_name must be non-empty string")
    matches = sorted(
        (w for w in writes if w.file_name == file_name),
        key=lambda w: w.sequence,
    )
    return "".join(w.data for w in matches)
