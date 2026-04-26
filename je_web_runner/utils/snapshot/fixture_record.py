"""
Record / replay fixture：第一次跑記錄回應，之後拿來當 fixture。
Record / replay fixture mode. The first invocation persists each
``key -> value`` pair to disk; subsequent invocations replay the saved
value, returning ``None`` if no recording is available.

Used to make flaky external dependencies deterministic: run once with
``RecorderMode.RECORD`` to capture, then ``RecorderMode.REPLAY`` everywhere
else.
"""
from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Union

from je_web_runner.utils.exception.exceptions import WebRunnerException


class FixtureRecorderError(WebRunnerException):
    """Raised when the recorder file cannot be read / written."""


class RecorderMode(Enum):
    RECORD = "record"
    REPLAY = "replay"
    AUTO = "auto"  # replay if recording exists, otherwise record


class FixtureRecorder:
    """Persist and replay key/value fixtures from a single JSON file."""

    def __init__(self, path: Union[str, Path], mode: RecorderMode = RecorderMode.AUTO) -> None:
        self.path = Path(path)
        self.mode = mode
        self._cache: Optional[Dict[str, Any]] = None
        self._dirty = False

    def _load(self) -> Dict[str, Any]:
        if self._cache is not None:
            return self._cache
        if not self.path.is_file():
            self._cache = {}
            return self._cache
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except ValueError as error:
            raise FixtureRecorderError(f"recorder file invalid JSON: {error}") from error
        if not isinstance(data, dict):
            raise FixtureRecorderError("recorder file must be a JSON object")
        self._cache = data
        return self._cache

    def has(self, key: str) -> bool:
        return key in self._load()

    def get(self, key: str) -> Any:
        cache = self._load()
        if key not in cache:
            raise FixtureRecorderError(f"no recording for key {key!r}")
        return cache[key]

    def set(self, key: str, value: Any) -> None:
        cache = self._load()
        cache[key] = value
        self._dirty = True

    def flush(self) -> None:
        if not self._dirty:
            return
        cache = self._cache or {}
        self.path.parent.mkdir(parents=True, exist_ok=True)  # NOSONAR — path is test-author input, not network-reachable
        self.path.write_text(  # NOSONAR — see comment above
            json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        self._dirty = False

    def replay_or_record(
        self,
        key: str,
        producer: Callable[[], Any],
    ) -> Any:
        """
        REPLAY 模式：取出存檔；RECORD：每次重錄；AUTO：缺則錄、有則放。
        ``RECORD`` always re-runs ``producer`` and saves; ``REPLAY`` reads
        only and raises if missing; ``AUTO`` replays when available, records
        otherwise.
        """
        if self.mode == RecorderMode.REPLAY:
            return self.get(key)
        if self.mode == RecorderMode.RECORD:
            value = producer()
            self.set(key, value)
            self.flush()
            return value
        # AUTO
        if self.has(key):
            return self.get(key)
        value = producer()
        self.set(key, value)
        self.flush()
        return value


def open_recorder(
    path: Union[str, Path],
    mode: Union[RecorderMode, str] = RecorderMode.AUTO,
) -> FixtureRecorder:
    """Convenience factory accepting string mode names."""
    if isinstance(mode, str):
        try:
            mode = RecorderMode(mode)
        except ValueError as error:
            raise FixtureRecorderError(
                f"unknown recorder mode {mode!r}; allowed: record/replay/auto"
            ) from error
    return FixtureRecorder(path=path, mode=mode)
