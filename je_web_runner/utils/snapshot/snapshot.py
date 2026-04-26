"""
文字 / DOM snapshot 測試：第一次執行寫入基準，往後比對。
Text / DOM snapshot testing. First run records the value as a baseline;
subsequent runs diff against it and raise on mismatch.

非 binary 友善：所有比對都以 UTF-8 字串進行，呼叫端自行序列化非字串資料。
String-only by design: callers serialise non-string values themselves
(json.dumps, html, etc.) so comparisons stay deterministic and human-readable.
"""
from __future__ import annotations

import difflib
from pathlib import Path
from typing import Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class SnapshotMismatch(WebRunnerException):
    """Raised when an existing snapshot does not match the candidate value."""


_DEFAULT_DIR = "snapshots"


def _snapshot_path(name: str, snapshot_dir: str) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in name)
    return Path(snapshot_dir) / f"{safe}.snap"


def _load(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def _write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def match_snapshot(
    name: str,
    value: str,
    snapshot_dir: str = _DEFAULT_DIR,
) -> str:
    """
    比對快照；首次執行會建立基準。
    Match ``value`` against the stored snapshot; on first run the snapshot is
    written and the return value is ``"created"``. On subsequent runs the
    return value is ``"matched"`` and a mismatch raises ``SnapshotMismatch``.

    :param name: 用於檔名的 snapshot 名稱（會做基本字元過濾）
    :param value: 要比對的字串
    :param snapshot_dir: 儲存目錄，預設 ``snapshots``
    """
    web_runner_logger.info(f"match_snapshot: {name}")
    if not isinstance(value, str):
        raise WebRunnerException(
            f"snapshot value must be str (got {type(value).__name__}); serialise it first"
        )
    target = _snapshot_path(name, snapshot_dir)
    existing = _load(target)
    if existing is None:
        _write(target, value)
        return "created"
    if existing == value:
        return "matched"
    diff = "".join(
        difflib.unified_diff(
            existing.splitlines(keepends=True),
            value.splitlines(keepends=True),
            fromfile=f"{name}.snap",
            tofile=f"{name}.candidate",
        )
    )
    raise SnapshotMismatch(f"snapshot mismatch for {name!r}:\n{diff}")


def update_snapshot(
    name: str,
    value: str,
    snapshot_dir: str = _DEFAULT_DIR,
) -> str:
    """
    強制覆蓋基準
    Overwrite the snapshot baseline with ``value``. Returns the file path.
    """
    web_runner_logger.info(f"update_snapshot: {name}")
    if not isinstance(value, str):
        raise WebRunnerException(
            f"snapshot value must be str (got {type(value).__name__}); serialise it first"
        )
    target = _snapshot_path(name, snapshot_dir)
    _write(target, value)
    return str(target)


def delete_snapshot(name: str, snapshot_dir: str = _DEFAULT_DIR) -> bool:
    """Remove a snapshot file; returns True if it existed."""
    target = _snapshot_path(name, snapshot_dir)
    if not target.exists():
        return False
    target.unlink()
    return True
