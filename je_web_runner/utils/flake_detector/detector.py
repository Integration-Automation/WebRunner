"""
Flaky test 偵測 + 自動隔離。

Flaky-test detection built on top of the ``run_ledger`` history. Two
ideas added on top of the existing :mod:`run_ledger.flaky` heuristic:

* **Time-decayed flake score** — recent flips count for more than ancient
  ones. Score is roughly ``hits / runs`` weighted by half-life decay.
* **Persistent quarantine registry** — JSON file tracking which tests are
  currently isolated and why. Stable across CI runs, sortable, releasable
  by hand or by ``release_if_stable`` once the score drops.

Plus a ``@flaky_quarantine`` decorator that defers to the registry at
runtime (skip with reason if the test id is currently quarantined).
"""
from __future__ import annotations

import functools
import json
import math
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class FlakeDetectorError(WebRunnerException):
    """Raised when ledger / registry I/O fails or input is malformed."""


_SECONDS_PER_DAY = 86_400.0
_DEFAULT_HALF_LIFE_DAYS = 7.0
_DEFAULT_MIN_RUNS = 3
_DEFAULT_FLAKE_THRESHOLD = 0.25


@dataclass
class FlakeScore:
    """Per-test rollup of the run history."""

    path: str
    runs: int
    passes: int
    fails: int
    pass_rate: float
    flake_score: float
    last_run: Optional[str] = None
    is_flaky: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _load_runs(ledger_path: Union[str, Path]) -> List[Dict[str, Any]]:
    path = Path(ledger_path)
    if not path.exists():
        return []
    try:
        with open(path, encoding="utf-8") as fp:
            data = json.load(fp)
    except (OSError, ValueError) as error:
        raise FlakeDetectorError(f"cannot read ledger {ledger_path}: {error!r}") from error
    if not isinstance(data, dict) or "runs" not in data:
        raise FlakeDetectorError(f"ledger missing 'runs' key: {ledger_path}")
    runs = data.get("runs")
    if not isinstance(runs, list):
        raise FlakeDetectorError(f"ledger 'runs' is not a list: {ledger_path}")
    return [r for r in runs if isinstance(r, dict)]


def _parse_run_time(value: Any, fallback_now: float) -> float:
    """Best-effort ISO-time → epoch seconds. Unknown formats fall back to ``now``."""
    if not isinstance(value, str) or not value:
        return fallback_now
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except ValueError:
        return fallback_now


def _decay_weight(age_seconds: float, half_life_days: float) -> float:
    if half_life_days <= 0:
        return 1.0
    half_life_seconds = half_life_days * _SECONDS_PER_DAY
    return math.pow(0.5, age_seconds / half_life_seconds)


def compute_flake_scores(  # NOSONAR S3776 — cohesive logic; planned refactor in follow-up
    ledger_path: Union[str, Path],
    *,
    half_life_days: float = _DEFAULT_HALF_LIFE_DAYS,
    min_runs: int = _DEFAULT_MIN_RUNS,
    threshold: float = _DEFAULT_FLAKE_THRESHOLD,
    now_epoch: Optional[float] = None,
) -> Dict[str, FlakeScore]:
    """
    從 ledger 歷史計算每個 file 的 time-decayed flake score。
    Produce per-file :class:`FlakeScore` records. A test is flagged ``is_flaky``
    when it has at least ``min_runs`` recorded runs AND its decayed flip rate
    exceeds ``threshold``. Pass rate is the *unweighted* ratio so dashboards
    stay readable.
    """
    runs = _load_runs(ledger_path)
    now = now_epoch if now_epoch is not None else time.time()
    buckets: Dict[str, Dict[str, Any]] = {}
    for run in runs:
        path = run.get("path")
        if not isinstance(path, str):
            continue
        record = buckets.setdefault(path, {
            "runs": 0, "passes": 0, "fails": 0,
            "weight_total": 0.0, "weight_fails": 0.0,
            "last_run": None,
        })
        record["runs"] += 1
        run_epoch = _parse_run_time(run.get("time"), now)
        age = max(0.0, now - run_epoch)
        weight = _decay_weight(age, half_life_days)
        record["weight_total"] += weight
        if run.get("passed"):
            record["passes"] += 1
        else:
            record["fails"] += 1
            record["weight_fails"] += weight
        last_run = run.get("time")
        if isinstance(last_run, str):
            existing = record["last_run"]
            if existing is None or last_run > existing:
                record["last_run"] = last_run

    out: Dict[str, FlakeScore] = {}
    for path, rec in buckets.items():
        runs_n = rec["runs"]
        passes = rec["passes"]
        fails = rec["fails"]
        pass_rate = (passes / runs_n) if runs_n else 0.0
        weight_total = rec["weight_total"]
        flake_score = (rec["weight_fails"] / weight_total) if weight_total else 0.0
        has_both = passes > 0 and fails > 0
        is_flaky = runs_n >= min_runs and has_both and flake_score >= threshold
        out[path] = FlakeScore(
            path=path,
            runs=runs_n,
            passes=passes,
            fails=fails,
            pass_rate=round(pass_rate, 4),
            flake_score=round(flake_score, 4),
            last_run=rec["last_run"],
            is_flaky=is_flaky,
        )
    return out


def flaky_paths(
    ledger_path: Union[str, Path],
    *,
    half_life_days: float = _DEFAULT_HALF_LIFE_DAYS,
    min_runs: int = _DEFAULT_MIN_RUNS,
    threshold: float = _DEFAULT_FLAKE_THRESHOLD,
) -> List[str]:
    """Return paths whose decayed flake score is at or above ``threshold``."""
    scores = compute_flake_scores(
        ledger_path,
        half_life_days=half_life_days,
        min_runs=min_runs,
        threshold=threshold,
    )
    flagged = [score for score in scores.values() if score.is_flaky]
    flagged.sort(key=lambda s: (-s.flake_score, s.path))
    return [s.path for s in flagged]


# ---------- quarantine registry ------------------------------------------

@dataclass
class QuarantineEntry:
    """One quarantined test record."""

    test_id: str
    reason: str
    flake_score: float
    quarantined_at: str
    runs_when_added: int = 0
    triage_url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


class QuarantineRegistry:
    """
    JSON-backed registry of currently quarantined tests.
    Stable across CI runs; intended to be checked into git or stored
    alongside the ledger so the pytest plugin can read it on every run.
    """

    def __init__(self, registry_path: Union[str, Path]) -> None:
        self.registry_path = Path(registry_path)
        self._entries: Dict[str, QuarantineEntry] = {}
        self._load()

    def _load(self) -> None:
        if not self.registry_path.exists():
            return
        try:
            with open(self.registry_path, encoding="utf-8") as fp:
                data = json.load(fp)
        except (OSError, ValueError) as error:
            raise FlakeDetectorError(
                f"cannot read quarantine registry {self.registry_path}: {error!r}"
            ) from error
        entries = data.get("entries") if isinstance(data, dict) else None
        if not isinstance(entries, list):
            raise FlakeDetectorError(
                f"registry missing 'entries' list: {self.registry_path}"
            )
        for entry in entries:
            if not isinstance(entry, dict) or "test_id" not in entry:
                continue
            self._entries[entry["test_id"]] = QuarantineEntry(
                test_id=str(entry["test_id"]),
                reason=str(entry.get("reason") or ""),
                flake_score=float(entry.get("flake_score") or 0.0),
                quarantined_at=str(entry.get("quarantined_at") or _utc_now_iso()),
                runs_when_added=int(entry.get("runs_when_added") or 0),
                triage_url=entry.get("triage_url"),
            )

    def _save(self) -> None:
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "updated_at": _utc_now_iso(),
            "entries": [e.to_dict() for e in self._entries.values()],
        }
        with open(self.registry_path, "w", encoding="utf-8") as fp:
            json.dump(payload, fp, ensure_ascii=False, indent=2)

    def is_quarantined(self, test_id: str) -> bool:
        return test_id in self._entries

    def get(self, test_id: str) -> Optional[QuarantineEntry]:
        return self._entries.get(test_id)

    def add(self, entry: QuarantineEntry) -> None:
        self._entries[entry.test_id] = entry
        self._save()
        web_runner_logger.info(
            f"quarantine add: {entry.test_id} reason={entry.reason!r} "
            f"score={entry.flake_score:.2f}"
        )

    def remove(self, test_id: str) -> bool:
        existing = self._entries.pop(test_id, None)
        if existing is None:
            return False
        self._save()
        web_runner_logger.info(f"quarantine remove: {test_id}")
        return True

    def list(self) -> List[QuarantineEntry]:
        return sorted(
            self._entries.values(),
            key=lambda e: (-e.flake_score, e.test_id),
        )


def quarantine_flaky(
    ledger_path: Union[str, Path],
    registry_path: Union[str, Path],
    *,
    half_life_days: float = _DEFAULT_HALF_LIFE_DAYS,
    min_runs: int = _DEFAULT_MIN_RUNS,
    threshold: float = _DEFAULT_FLAKE_THRESHOLD,
    reason_template: str = "auto: flake_score={score:.2f} after {runs} runs",
) -> List[str]:
    """
    自動把 flake score ≥ threshold 的 test 加入 quarantine registry。
    Walk the ledger, score each test, and write any newly-flaky tests into
    the registry. Returns the list of newly-quarantined test ids (already-
    quarantined tests are left alone — their original metadata persists).
    """
    scores = compute_flake_scores(
        ledger_path,
        half_life_days=half_life_days,
        min_runs=min_runs,
        threshold=threshold,
    )
    registry = QuarantineRegistry(registry_path)
    newly_added: List[str] = []
    for score in scores.values():
        if not score.is_flaky:
            continue
        if registry.is_quarantined(score.path):
            continue
        entry = QuarantineEntry(
            test_id=score.path,
            reason=reason_template.format(score=score.flake_score, runs=score.runs),
            flake_score=score.flake_score,
            quarantined_at=_utc_now_iso(),
            runs_when_added=score.runs,
        )
        registry.add(entry)
        newly_added.append(score.path)
    return newly_added


def release_if_stable(
    ledger_path: Union[str, Path],
    registry_path: Union[str, Path],
    *,
    half_life_days: float = _DEFAULT_HALF_LIFE_DAYS,
    release_threshold: float = 0.05,
    min_runs_since: int = 5,
) -> List[str]:
    """
    放出 flake score 已穩定下降到 ``release_threshold`` 以下的 quarantine test。
    Promote stable tests out of quarantine: each entry whose current score
    is below ``release_threshold`` AND has been observed ``min_runs_since``
    times in the ledger is removed. Returns the released test ids.
    """
    scores = compute_flake_scores(
        ledger_path,
        half_life_days=half_life_days,
        min_runs=min_runs_since,
        threshold=release_threshold + 1.0,  # ensure is_flaky=False is meaningful
    )
    registry = QuarantineRegistry(registry_path)
    released: List[str] = []
    for entry in registry.list():
        current = scores.get(entry.test_id)
        if current is None:
            continue
        if current.runs < min_runs_since:
            continue
        if current.flake_score <= release_threshold:
            if registry.remove(entry.test_id):
                released.append(entry.test_id)
    return released


# ---------- decorator -----------------------------------------------------

def flaky_quarantine(
    test_id: str,
    registry_path: Union[str, Path],
    *,
    skip_when_quarantined: bool = True,
) -> Callable:
    """
    Decorator：執行前查 quarantine registry，若被隔離則 skip 並標明原因。
    Wrap a callable (typically a pytest test function). At call time, look
    up the registry; if the test id is quarantined, skip with the reason
    string when ``skip_when_quarantined`` is true, else just log it and run.

    Skipping uses ``pytest.skip`` when pytest is importable; falls back to
    raising :class:`FlakeDetectorError` otherwise so non-pytest harnesses can
    detect and handle the quarantine themselves.
    """
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            registry = QuarantineRegistry(registry_path)
            entry = registry.get(test_id)
            if entry is None:
                return fn(*args, **kwargs)
            web_runner_logger.warning(
                f"flaky_quarantine: {test_id} is quarantined ({entry.reason})"
            )
            if not skip_when_quarantined:
                return fn(*args, **kwargs)
            try:
                import pytest  # local import keeps decorator pytest-optional
            except ImportError as import_error:
                raise FlakeDetectorError(
                    f"test {test_id!r} is quarantined: {entry.reason}"
                ) from import_error
            pytest.skip(f"flaky-quarantine: {entry.reason}")
            return None
        return wrapper
    return decorator


# ---------- reporting ----------------------------------------------------

def quarantine_report_markdown(registry: QuarantineRegistry) -> str:
    """Render the current quarantine list as a markdown table."""
    entries = registry.list()
    if not entries:
        return "_No quarantined tests._\n"
    rows = [
        "| Test | Score | Reason | Since |",
        "|------|-------|--------|-------|",
    ]
    for entry in entries:
        rows.append(
            f"| `{entry.test_id}` | {entry.flake_score:.2f} | "
            f"{entry.reason} | {entry.quarantined_at} |"
        )
    return "\n".join(rows) + "\n"
