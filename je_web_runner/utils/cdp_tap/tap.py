"""
CDP message tap：把 ``execute_cdp_cmd`` 的呼叫與回傳全錄成 ndjson；之後可離線 replay。
Lightweight CDP traffic recorder. Wraps ``driver.execute_cdp_cmd`` so
every ``(method, params, returnValue, exception)`` triple is appended to
an ndjson log. The replayer feeds the same sequence back to a stub
driver for offline failure analysis.

Designed for Selenium 4's CDP shim and Playwright's ``send`` /
``receive`` pair. Both backends share a common adapter.
"""
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Union

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class CdpTapError(WebRunnerException):
    """Raised when recording or replay can't proceed."""


@dataclass
class CdpRecord:
    timestamp: float
    method: str
    params: Dict[str, Any]
    return_value: Any = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "method": self.method,
            "params": self.params,
            "return_value": self.return_value,
            "error": self.error,
        }


@dataclass
class CdpRecorder:
    """Wrap a driver's ``execute_cdp_cmd`` and persist every call."""

    output_path: Union[str, Path]
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _records: List[CdpRecord] = field(default_factory=list, init=False, repr=False)

    def attach(self, driver: Any) -> Callable[[str, Dict[str, Any]], Any]:
        """
        Replace ``driver.execute_cdp_cmd`` with a recording wrapper. Returns
        the *original* method so the caller can ``detach`` later.
        """
        if not hasattr(driver, "execute_cdp_cmd"):
            raise CdpTapError("driver does not expose execute_cdp_cmd")
        original = driver.execute_cdp_cmd

        def recorded(method: str, params: Optional[Dict[str, Any]] = None) -> Any:
            return self._invoke(original, method, params or {})

        driver.execute_cdp_cmd = recorded  # type: ignore[assignment]
        return original

    def detach(self, driver: Any, original: Callable[[str, Dict[str, Any]], Any]) -> None:
        driver.execute_cdp_cmd = original  # type: ignore[assignment]
        self.flush()

    def _invoke(self, original: Callable, method: str, params: Dict[str, Any]) -> Any:
        timestamp = time.time()
        try:
            value = original(method, params)
        except Exception as error:  # pylint: disable=broad-except
            self._append(CdpRecord(
                timestamp=timestamp,
                method=method,
                params=params,
                error=repr(error),
            ))
            raise
        try:
            json.dumps(value)
            recorded_value = value
        except (TypeError, ValueError):
            recorded_value = repr(value)[:1000]
        self._append(CdpRecord(
            timestamp=timestamp,
            method=method,
            params=params,
            return_value=recorded_value,
        ))
        return value

    def _append(self, record: CdpRecord) -> None:
        with self._lock:
            self._records.append(record)

    def flush(self) -> Path:
        path = Path(self.output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, open(path, "w", encoding="utf-8") as handle:
            for record in self._records:
                handle.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
        web_runner_logger.info(f"cdp_tap flushed {len(self._records)} record(s) to {path}")
        return path

    def records(self) -> List[CdpRecord]:
        return list(self._records)


def load_recording(path: Union[str, Path]) -> List[CdpRecord]:
    fp = Path(path)
    if not fp.is_file():
        raise CdpTapError(f"recording file not found: {path!r}")
    records: List[CdpRecord] = []
    for line_no, line in enumerate(fp.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except ValueError as error:
            raise CdpTapError(
                f"recording line {line_no} not JSON: {error}"
            ) from error
        records.append(CdpRecord(
            timestamp=float(data.get("timestamp", 0)),
            method=str(data.get("method", "")),
            params=data.get("params") or {},
            return_value=data.get("return_value"),
            error=data.get("error"),
        ))
    return records


@dataclass
class CdpReplayer:
    """Match incoming ``execute_cdp_cmd`` calls against a recording."""

    records: List[CdpRecord]
    _cursor: int = field(default=0, init=False)

    def execute_cdp_cmd(self, method: str, params: Optional[Dict[str, Any]] = None) -> Any:
        if self._cursor >= len(self.records):
            raise CdpTapError("replay exhausted; no more recorded entries")
        record = self.records[self._cursor]
        self._cursor += 1
        if record.method != method:
            raise CdpTapError(
                f"replay drift at #{self._cursor - 1}: "
                f"recorded {record.method!r}, called {method!r}"
            )
        if record.error is not None:
            raise CdpTapError(f"recorded error replayed: {record.error}")
        return record.return_value

    def reset(self) -> None:
        self._cursor = 0

    def remaining(self) -> int:
        return max(0, len(self.records) - self._cursor)
