"""
Watch mode：監聽 action JSON 目錄變更，自動重跑（debounced）。
Watch mode for the CLI: poll an action-JSON directory and re-run when files
change. Uses stdlib polling so no extra dependency is required.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Dict

from je_web_runner.utils.logging.loggin_instance import web_runner_logger


def _snapshot(directory: str) -> Dict[str, float]:
    """Map of relative path → mtime for every JSON file under ``directory``."""
    base = Path(directory)
    snapshot: Dict[str, float] = {}
    for path in base.rglob("*.json"):
        try:
            snapshot[str(path)] = path.stat().st_mtime
        except OSError:
            continue
    return snapshot


def watch_directory(
    directory: str,
    runner: Callable[[], None],
    poll_seconds: float = 0.5,
    debounce_seconds: float = 0.5,
    iterations: int = 0,
) -> int:
    """
    監聽 ``directory`` 內的 JSON 檔案，變更時呼叫 ``runner``
    Poll ``directory`` and call ``runner`` on each change burst. Returns the
    number of times ``runner`` was invoked.

    :param poll_seconds: 兩次掃描間隔 / interval between snapshots
    :param debounce_seconds: 偵測到變更後等待此秒數聚合多個變更
                              after the first change, wait this long before
                              firing so multiple writes coalesce into one run
    :param iterations: 0 表示無窮（直到 KeyboardInterrupt），> 0 用於測試
                        0 means "run forever"; > 0 limits the loop for tests
    """
    web_runner_logger.info(f"watch_directory: {directory}")
    base = Path(directory)
    if not base.is_dir():
        raise FileNotFoundError(f"watch directory not found: {directory}")
    runs = 0
    last_snapshot = _snapshot(directory)

    # Initial run so users always see baseline output once.
    runner()
    runs += 1

    counter = 0
    try:
        while iterations == 0 or counter < iterations:
            counter += 1
            time.sleep(poll_seconds)
            current = _snapshot(directory)
            if current == last_snapshot:
                continue
            # Debounce: take a second snapshot after a brief pause and only
            # run when the directory has settled.
            time.sleep(debounce_seconds)
            settled = _snapshot(directory)
            if settled != current:
                # still changing; defer to next poll cycle
                last_snapshot = settled
                continue
            web_runner_logger.info("watch_directory: change detected, re-running")
            runner()
            runs += 1
            last_snapshot = settled
    except KeyboardInterrupt:
        web_runner_logger.info("watch_directory: stopped via KeyboardInterrupt")
    return runs
