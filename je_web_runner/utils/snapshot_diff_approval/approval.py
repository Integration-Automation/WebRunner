"""
Visual / text snapshot diff + approval workflow.

Maintains an on-disk register of snapshots with three states:

* **baseline** — committed reference. CI diffs against this.
* **pending** — produced by a test run that doesn't match the baseline;
  needs human review before promotion to baseline.
* **rejected** — explicitly rejected (kept for audit / blame).

Workflow helpers: ``capture``, ``compare`` (returns ``DiffResult``),
``approve``, ``reject``, ``list_pending``. Bytes/text comparison only —
visual pixel diff is delegated to [[visual_ai]].
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException


class SnapshotDiffApprovalError(WebRunnerException):
    """Raised on malformed input or invalid state transitions."""


class Status(str, Enum):
    BASELINE = "baseline"
    PENDING = "pending"
    REJECTED = "rejected"


@dataclass
class SnapshotEntry:
    name: str
    sha256: str
    status: Status
    updated_at: str
    approved_by: str = ""
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {**asdict(self), "status": self.status.value}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0, tzinfo=None).isoformat() + "Z"


def _hash(payload: bytes) -> str:
    if not isinstance(payload, (bytes, bytearray)):
        raise SnapshotDiffApprovalError("payload must be bytes")
    return hashlib.sha256(bytes(payload)).hexdigest()


@dataclass
class DiffResult:
    name: str
    baseline_sha: str
    head_sha: str

    @property
    def changed(self) -> bool:
        return self.baseline_sha != self.head_sha


def load(path: str) -> Dict[str, SnapshotEntry]:
    if not isinstance(path, str) or not path:
        raise SnapshotDiffApprovalError("path must be non-empty string")
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    if not isinstance(raw, dict):
        raise SnapshotDiffApprovalError(
            f"registry file {path!r} must contain a JSON object"
        )
    out: Dict[str, SnapshotEntry] = {}
    for name, item in raw.items():
        if not isinstance(item, dict):
            continue
        out[name] = SnapshotEntry(
            name=name,
            sha256=str(item.get("sha256") or ""),
            status=Status(item.get("status", Status.PENDING.value)),
            updated_at=str(item.get("updated_at") or _now()),
            approved_by=str(item.get("approved_by") or ""),
            note=str(item.get("note") or ""),
        )
    return out


def save(path: str, registry: Dict[str, SnapshotEntry]) -> None:
    if not isinstance(path, str) or not path:
        raise SnapshotDiffApprovalError("path must be non-empty string")
    serialised = {name: e.to_dict() for name, e in registry.items()}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(serialised, fh, indent=2, sort_keys=True)


def capture(
    registry: Dict[str, SnapshotEntry], *, name: str, payload: bytes,
) -> DiffResult:
    """Compare ``payload`` against baseline. If no baseline exists, the
    snapshot enters as ``pending``."""
    if not name:
        raise SnapshotDiffApprovalError("name must be non-empty")
    head = _hash(payload)
    existing = registry.get(name)
    if existing and existing.status == Status.BASELINE:
        if existing.sha256 == head:
            return DiffResult(name=name,
                              baseline_sha=existing.sha256, head_sha=head)
        registry[name] = SnapshotEntry(
            name=name, sha256=head, status=Status.PENDING,
            updated_at=_now(), note="auto-captured on mismatch",
        )
        return DiffResult(name=name,
                          baseline_sha=existing.sha256, head_sha=head)
    registry[name] = SnapshotEntry(
        name=name, sha256=head, status=Status.PENDING,
        updated_at=_now(),
    )
    return DiffResult(name=name, baseline_sha="", head_sha=head)


def approve(
    registry: Dict[str, SnapshotEntry], *, name: str, reviewer: str,
) -> SnapshotEntry:
    entry = registry.get(name)
    if entry is None:
        raise SnapshotDiffApprovalError(f"unknown snapshot {name!r}")
    if entry.status != Status.PENDING:
        raise SnapshotDiffApprovalError(
            f"snapshot {name!r} is not pending (status={entry.status.value})"
        )
    if not reviewer:
        raise SnapshotDiffApprovalError("reviewer must be non-empty")
    entry.status = Status.BASELINE
    entry.approved_by = reviewer
    entry.updated_at = _now()
    return entry


def reject(
    registry: Dict[str, SnapshotEntry], *, name: str,
    reviewer: str, note: str = "",
) -> SnapshotEntry:
    entry = registry.get(name)
    if entry is None:
        raise SnapshotDiffApprovalError(f"unknown snapshot {name!r}")
    if not reviewer:
        raise SnapshotDiffApprovalError("reviewer must be non-empty")
    entry.status = Status.REJECTED
    entry.approved_by = reviewer
    entry.updated_at = _now()
    if note:
        entry.note = note
    return entry


def list_pending(registry: Dict[str, SnapshotEntry]) -> List[SnapshotEntry]:
    return [e for e in registry.values() if e.status == Status.PENDING]


def assert_no_pending(registry: Dict[str, SnapshotEntry]) -> None:
    pending = list_pending(registry)
    if pending:
        names = [e.name for e in pending]
        raise SnapshotDiffApprovalError(
            f"{len(pending)} snapshot(s) pending review: {names}"
        )
