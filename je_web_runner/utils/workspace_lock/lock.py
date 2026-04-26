"""
Workspace lock file：把 pip 套件版本 + driver 版本 + Playwright browser 版本綁在一起，
讓 CI 完全 reproducible。
Workspace lock file. Records every dependency layer that affects the
test outcome:

- ``python``: package + version pinned to the active interpreter, plus
  every installed distribution (parsed from ``importlib.metadata``).
- ``drivers``: pinned ``geckodriver`` / ``chromedriver`` / ``msedgedriver``
  via the existing ``driver_pin`` shape.
- ``playwright``: optional browser-engine version triple.

The format is JSON so it diffs cleanly in PRs and survives every editor.
"""
from __future__ import annotations

import datetime as _dt
import json
import sys
from dataclasses import asdict, dataclass, field
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

from je_web_runner.utils.exception.exceptions import WebRunnerException


class WorkspaceLockError(WebRunnerException):
    """Raised on invalid lock content or missing target."""


@dataclass(frozen=True)
class LockEntry:
    """A pinned dependency layer."""

    name: str
    version: str
    kind: str  # "python" / "driver" / "playwright"
    extras: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkspaceLock:
    python_version: str
    generated_at: str
    entries: List[LockEntry] = field(default_factory=list)

    def by_kind(self, kind: str) -> List[LockEntry]:
        return [entry for entry in self.entries if entry.kind == kind]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "python_version": self.python_version,
            "generated_at": self.generated_at,
            "entries": [asdict(entry) for entry in self.entries],
        }


def _python_runtime_version() -> str:
    info = sys.version_info
    return f"{info.major}.{info.minor}.{info.micro}"


_DISTRIBUTION_CACHE: Optional[List[tuple]] = None


def _scan_distributions() -> List[tuple]:
    """Walk ``importlib.metadata`` once and cache the (name, version) tuples."""
    global _DISTRIBUTION_CACHE
    if _DISTRIBUTION_CACHE is not None:
        return _DISTRIBUTION_CACHE
    scanned: List[tuple] = []
    for dist in importlib_metadata.distributions():
        try:
            name = dist.metadata.get("Name") or ""
            version = dist.version or ""
        except Exception:  # pylint: disable=broad-except
            continue
        if not name or not version:
            continue
        scanned.append((name, version))
    _DISTRIBUTION_CACHE = scanned
    return scanned


def reset_distribution_cache() -> None:
    """Clear the cached distribution list (useful in tests / venv reloads)."""
    global _DISTRIBUTION_CACHE
    _DISTRIBUTION_CACHE = None


def _python_distributions(allow_distributions: Optional[Iterable[str]] = None) -> List[LockEntry]:
    entries: List[LockEntry] = []
    seen: set = set()
    allow = set(allow_distributions) if allow_distributions else None
    for name, version in _scan_distributions():
        normalised = name.lower().replace("_", "-")
        if normalised in seen:
            continue
        if allow is not None and normalised not in {a.lower() for a in allow}:
            continue
        seen.add(normalised)
        entries.append(LockEntry(name=normalised, version=version, kind="python"))
    return sorted(entries, key=lambda e: e.name)


def build_lock(
    drivers: Optional[Iterable[Dict[str, Any]]] = None,
    playwright_versions: Optional[Dict[str, str]] = None,
    allow_distributions: Optional[Iterable[str]] = None,
    now: Optional[_dt.datetime] = None,
) -> WorkspaceLock:
    """
    Build a :class:`WorkspaceLock` from the active interpreter + caller-supplied
    driver / Playwright versions.
    """
    entries: List[LockEntry] = []
    entries.extend(_python_distributions(allow_distributions=allow_distributions))
    for driver_entry in drivers or []:
        if not isinstance(driver_entry, dict) or not driver_entry.get("name") or not driver_entry.get("version"):
            raise WorkspaceLockError(
                f"driver entry must include name + version: {driver_entry!r}"
            )
        extras = {k: v for k, v in driver_entry.items() if k not in {"name", "version"}}
        entries.append(LockEntry(
            name=str(driver_entry["name"]),
            version=str(driver_entry["version"]),
            kind="driver",
            extras=extras,
        ))
    for browser, version in (playwright_versions or {}).items():
        if not isinstance(browser, str) or not isinstance(version, str):
            raise WorkspaceLockError(
                f"playwright entry must be (str, str): ({browser!r}, {version!r})"
            )
        entries.append(LockEntry(
            name=browser, version=version, kind="playwright",
        ))
    timestamp = (now or _dt.datetime.now(tz=_dt.timezone.utc)).isoformat(timespec="seconds")
    return WorkspaceLock(
        python_version=_python_runtime_version(),
        generated_at=timestamp,
        entries=entries,
    )


def write_lock(lock: WorkspaceLock, path: Union[str, Path]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(lock.to_dict(), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return target


def load_lock(path: Union[str, Path]) -> WorkspaceLock:
    fp = Path(path)
    if not fp.is_file():
        raise WorkspaceLockError(f"lock file not found: {path!r}")
    try:
        document = json.loads(fp.read_text(encoding="utf-8"))
    except ValueError as error:
        raise WorkspaceLockError(f"lock file invalid JSON: {error}") from error
    if not isinstance(document, dict):
        raise WorkspaceLockError("lock root must be an object")
    raw_entries = document.get("entries")
    if not isinstance(raw_entries, list):
        raise WorkspaceLockError("lock 'entries' must be a list")
    entries: List[LockEntry] = []
    for index, entry in enumerate(raw_entries):
        if not isinstance(entry, dict):
            raise WorkspaceLockError(f"entries[{index}] must be an object")
        try:
            entries.append(LockEntry(
                name=str(entry["name"]),
                version=str(entry["version"]),
                kind=str(entry["kind"]),
                extras=entry.get("extras") or {},
            ))
        except KeyError as error:
            raise WorkspaceLockError(
                f"entries[{index}] missing key {error.args[0]!r}"
            ) from error
    return WorkspaceLock(
        python_version=str(document.get("python_version") or ""),
        generated_at=str(document.get("generated_at") or ""),
        entries=entries,
    )


def diff_locks(before: WorkspaceLock, after: WorkspaceLock) -> Dict[str, List[Dict[str, Any]]]:
    """
    Compare two locks and return ``{added, removed, version_changed}`` lists.
    """
    before_index = {(e.name, e.kind): e for e in before.entries}
    after_index = {(e.name, e.kind): e for e in after.entries}
    added = [asdict(after_index[k]) for k in sorted(after_index.keys() - before_index.keys())]
    removed = [asdict(before_index[k]) for k in sorted(before_index.keys() - after_index.keys())]
    changed: List[Dict[str, Any]] = []
    for key in sorted(before_index.keys() & after_index.keys()):
        if before_index[key].version != after_index[key].version:
            changed.append({
                "name": key[0], "kind": key[1],
                "from": before_index[key].version,
                "to": after_index[key].version,
            })
    return {"added": added, "removed": removed, "version_changed": changed}
