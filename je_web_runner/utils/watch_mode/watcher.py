"""
檔案監看：偵測指定目錄下的 JSON 檔案變動，觸發 callback 重跑。
Lightweight directory watcher. Snapshots ``(path, mtime, size)`` for every
file matching ``*.json`` (or any glob) and reports diffs vs. a previous
snapshot. Callers chain it into a loop with ``watch_loop``.

Pure stdlib so the runtime dependency stays minimal; if you need
inotify-grade events, plug a real watcher into ``poll_changes``.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class WatchModeError(WebRunnerException):
    """Raised on bad inputs to the watcher."""


@dataclass
class WatchSnapshot:
    """``{path: (mtime, size)}`` snapshot of a directory tree."""

    entries: Dict[str, Tuple[float, int]] = field(default_factory=dict)


def snapshot_dir(directory: str, glob: str = "**/*.json") -> WatchSnapshot:
    base = Path(directory)
    if not base.is_dir():
        raise WatchModeError(f"watch directory missing: {directory!r}")
    snapshot = WatchSnapshot()
    for path in base.glob(glob):
        if not path.is_file():
            continue
        stat = path.stat()
        snapshot.entries[str(path)] = (stat.st_mtime, stat.st_size)
    return snapshot


@dataclass
class WatchDiff:
    added: List[str] = field(default_factory=list)
    removed: List[str] = field(default_factory=list)
    changed: List[str] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.removed or self.changed)


def poll_changes(previous: WatchSnapshot, current: WatchSnapshot) -> WatchDiff:
    diff = WatchDiff()
    prev_keys = set(previous.entries.keys())
    curr_keys = set(current.entries.keys())
    diff.added = sorted(curr_keys - prev_keys)
    diff.removed = sorted(prev_keys - curr_keys)
    for key in sorted(prev_keys & curr_keys):
        if previous.entries[key] != current.entries[key]:
            diff.changed.append(key)
    return diff


def watch_loop(
    directory: str,
    on_change: Callable[[WatchDiff], None],
    glob: str = "**/*.json",
    interval: float = 0.5,
    max_iterations: Optional[int] = None,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """
    在 ``directory`` 上輪詢，每次有變動就 ``on_change(diff)``
    Poll the directory at ``interval`` seconds. Calls ``on_change(diff)``
    only when something changed; returns the iteration count.
    """
    previous = snapshot_dir(directory, glob=glob)
    iterations = 0
    while max_iterations is None or iterations < max_iterations:
        sleep(interval)
        iterations += 1
        current = snapshot_dir(directory, glob=glob)
        diff = poll_changes(previous, current)
        if diff.has_changes:
            web_runner_logger.info(
                f"watch_loop iteration={iterations} added={len(diff.added)} "
                f"removed={len(diff.removed)} changed={len(diff.changed)}"
            )
            on_change(diff)
            previous = current
    return iterations
