"""
跑測試後紀錄每個 action 檔的 pass / fail，供 --rerun-failed 使用。
Per-file pass/fail ledger for ``--rerun-failed`` and other historical
queries. Stored as a single JSON document so it round-trips cleanly with
git or CI artefact storage.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class LedgerError(WebRunnerException):
    """Raised on ledger I/O / format problems."""


def _load(ledger_path: str) -> Dict[str, list]:
    path = Path(ledger_path)
    if not path.exists():
        return {"runs": []}
    try:
        with open(path, encoding="utf-8") as ledger_file:
            data = json.load(ledger_file)
    except ValueError as error:
        raise LedgerError(f"ledger file is not valid JSON: {ledger_path}") from error
    if not isinstance(data, dict) or "runs" not in data:
        raise LedgerError(f"ledger file missing 'runs' list: {ledger_path}")
    return data


def _save(ledger_path: str, data: Dict[str, list]) -> None:
    path = Path(ledger_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as ledger_file:
        json.dump(data, ledger_file, indent=2)


def record_run(ledger_path: str, file_path: str, passed: bool) -> None:
    """Append one run record to the ledger."""
    web_runner_logger.info(f"record_run: {file_path} passed={passed}")
    data = _load(ledger_path)
    data["runs"].append({
        "path": str(file_path),
        "passed": bool(passed),
        "time": datetime.now().isoformat(timespec="seconds"),
    })
    _save(ledger_path, data)


def latest_status(ledger_path: str) -> Dict[str, bool]:
    """
    取每個檔案最新的 pass/fail 狀態
    Build a dict keyed by file path of the most recent passed flag.
    """
    data = _load(ledger_path)
    latest: Dict[str, bool] = {}
    for run in data["runs"]:
        path = run.get("path")
        if isinstance(path, str):
            latest[path] = bool(run.get("passed"))
    return latest


def failed_files(ledger_path: str) -> List[str]:
    """Return paths whose most recent run was a failure."""
    return [path for path, passed in latest_status(ledger_path).items() if not passed]


def passed_files(ledger_path: str) -> List[str]:
    """Return paths whose most recent run was a pass."""
    return [path for path, passed in latest_status(ledger_path).items() if passed]


def clear_ledger(ledger_path: str) -> None:
    """Delete the ledger file (no-op if missing)."""
    path = Path(ledger_path)
    if path.exists():
        path.unlink()
