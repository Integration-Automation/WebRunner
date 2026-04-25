"""
HAR 檔案差異比對：用 (method, url) 作 key，回傳新增 / 移除 / 狀態碼變動。
HAR file diff utility. Keyed by (method, url); reports added, removed, and
status-changed requests between two HAR documents.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class HarDiffError(WebRunnerException):
    """Raised when a HAR document cannot be parsed."""


_Entry = Dict[str, Any]


def _load_har(har: Any) -> Dict[str, Any]:
    if isinstance(har, dict):
        return har
    if isinstance(har, str):
        try:
            return json.loads(har)
        except ValueError as error:
            raise HarDiffError(f"invalid HAR JSON: {error}") from error
    raise HarDiffError(f"unsupported HAR type: {type(har).__name__}")


def _entries(har: Dict[str, Any]) -> List[_Entry]:
    log = har.get("log")
    if not isinstance(log, dict):
        raise HarDiffError("HAR missing 'log' block")
    entries = log.get("entries", [])
    if not isinstance(entries, list):
        raise HarDiffError("HAR 'log.entries' is not a list")
    return entries


def _index(entries: List[_Entry]) -> Dict[Tuple[str, str], _Entry]:
    """Index entries by (METHOD, url); later entries with the same key win."""
    index: Dict[Tuple[str, str], _Entry] = {}
    for entry in entries:
        request = entry.get("request") or {}
        method = (request.get("method") or "").upper()
        url = request.get("url") or ""
        if method or url:
            index[(method, url)] = entry
    return index


def _status(entry: _Entry) -> int:
    response = entry.get("response") or {}
    status = response.get("status")
    return int(status) if isinstance(status, int) else 0


def diff_har(left: Any, right: Any) -> Dict[str, List[Dict[str, Any]]]:
    """
    比對兩份 HAR；回傳 ``{added, removed, changed}``
    Diff two HAR documents; returns ``{added, removed, changed}`` lists.
    """
    web_runner_logger.info("diff_har")
    left_index = _index(_entries(_load_har(left)))
    right_index = _index(_entries(_load_har(right)))

    added: List[Dict[str, Any]] = []
    removed: List[Dict[str, Any]] = []
    changed: List[Dict[str, Any]] = []

    for key, entry in right_index.items():
        if key not in left_index:
            added.append({"method": key[0], "url": key[1], "status": _status(entry)})

    for key, entry in left_index.items():
        if key not in right_index:
            removed.append({"method": key[0], "url": key[1], "status": _status(entry)})

    for key, left_entry in left_index.items():
        if key not in right_index:
            continue
        right_entry = right_index[key]
        left_status = _status(left_entry)
        right_status = _status(right_entry)
        if left_status != right_status:
            changed.append({
                "method": key[0],
                "url": key[1],
                "left_status": left_status,
                "right_status": right_status,
            })

    return {"added": added, "removed": removed, "changed": changed}


def diff_har_files(left_path: str, right_path: str) -> Dict[str, List[Dict[str, Any]]]:
    """讀取兩個 HAR 檔並比對 / Read two HAR files from disk and diff them."""
    left_path_obj = Path(left_path)
    right_path_obj = Path(right_path)
    if not left_path_obj.exists():
        raise HarDiffError(f"HAR file not found: {left_path}")
    if not right_path_obj.exists():
        raise HarDiffError(f"HAR file not found: {right_path}")
    return diff_har(
        left_path_obj.read_text(encoding="utf-8"),
        right_path_obj.read_text(encoding="utf-8"),
    )
