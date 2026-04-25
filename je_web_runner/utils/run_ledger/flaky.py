"""
從 ledger 歷史計算 flaky（同一檔案有時過、有時失敗）統計。
Compute flakiness statistics from the run ledger: same file passing on some
runs and failing on others.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class FlakyDetectorError(WebRunnerException):
    """Raised when the ledger cannot be read."""


def _load_runs(ledger_path: str) -> List[dict]:
    path = Path(ledger_path)
    if not path.exists():
        return []
    try:
        with open(path, encoding="utf-8") as ledger_file:
            data = json.load(ledger_file)
    except ValueError as error:
        raise FlakyDetectorError(f"ledger not valid JSON: {ledger_path}") from error
    if not isinstance(data, dict) or "runs" not in data:
        raise FlakyDetectorError(f"ledger missing 'runs' list: {ledger_path}")
    return [run for run in data["runs"] if isinstance(run, dict)]


def flakiness_stats(ledger_path: str, min_runs: int = 3) -> Dict[str, Dict[str, int]]:
    """
    從 ledger 算出每個檔案的 ``{runs, passes, fails, flaky}`` 統計
    Compute per-file run / pass / fail counts plus a ``flaky`` flag.
    A file is flaky when it has at least ``min_runs`` runs AND has both
    passes and fails in its history.
    """
    runs = _load_runs(ledger_path)
    counters: Dict[str, Dict[str, int]] = defaultdict(lambda: {"runs": 0, "passes": 0, "fails": 0})
    for run in runs:
        path = run.get("path")
        if not isinstance(path, str):
            continue
        counters[path]["runs"] += 1
        if run.get("passed"):
            counters[path]["passes"] += 1
        else:
            counters[path]["fails"] += 1

    result: Dict[str, Dict[str, int]] = {}
    for path, stats in counters.items():
        flaky = stats["runs"] >= min_runs and stats["passes"] > 0 and stats["fails"] > 0
        stats_with_flag = dict(stats)
        stats_with_flag["flaky"] = bool(flaky)
        result[path] = stats_with_flag
    return result


def flaky_paths(
    ledger_path: str,
    min_runs: int = 3,
    min_fail_rate: float = 0.0,
) -> List[str]:
    """
    回傳被判為 flaky 的檔案
    Return the file paths that the heuristic considers flaky.

    :param min_runs: 至少執行幾次才考慮判定 / minimum number of runs required
    :param min_fail_rate: 失敗率下限（0.0–1.0），低於此值不判 flaky
    """
    web_runner_logger.info(
        f"flaky_paths min_runs={min_runs} min_fail_rate={min_fail_rate}"
    )
    stats = flakiness_stats(ledger_path, min_runs=min_runs)
    out: List[str] = []
    for path, info in stats.items():
        if not info["flaky"]:
            continue
        fail_rate = info["fails"] / info["runs"] if info["runs"] else 0.0
        if fail_rate < min_fail_rate:
            continue
        out.append(path)
    return out
