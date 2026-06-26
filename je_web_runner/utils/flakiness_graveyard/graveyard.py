"""
Flakiness graveyard registry.

Tests that have been quarantined long enough — without resurrection or
fixing — are scheduled for deletion. The registry is a JSON-on-disk
file (no DB dependency); each entry records:

* ``test_name``
* ``quarantined_at`` (ISO date)
* ``last_flake_date``
* ``owner``  (so PR auto-assign knows who to ping)
* ``ticket_url``
* ``status``: ``quarantined`` | ``revived`` | ``buried``

Common ops: ``register_flake``, ``promote_to_grave``, ``revive``,
``due_for_burial``.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Iterable

from je_web_runner.utils.exception.exceptions import WebRunnerException


class FlakinessGraveyardError(WebRunnerException):
    """Raised on malformed entries or invalid transitions."""


class Status(str, Enum):
    QUARANTINED = "quarantined"
    REVIVED = "revived"
    BURIED = "buried"


@dataclass
class GraveEntry:
    test_name: str
    quarantined_at: str
    last_flake_date: str
    owner: str = ""
    ticket_url: str = ""
    status: Status = Status.QUARANTINED

    def __post_init__(self) -> None:
        if not self.test_name:
            raise FlakinessGraveyardError("test_name must be non-empty")
        _parse_date(self.quarantined_at, "quarantined_at")
        _parse_date(self.last_flake_date, "last_flake_date")

    def to_dict(self) -> dict[str, str]:
        return {**asdict(self), "status": self.status.value}


def _parse_date(value: str, field_name: str) -> date:
    if not isinstance(value, str):
        raise FlakinessGraveyardError(
            f"{field_name} must be ISO date string"
        )
    try:
        return datetime.fromisoformat(value).date()
    except ValueError as exc:
        raise FlakinessGraveyardError(
            f"{field_name} not parseable: {value!r}"
        ) from exc


def _today() -> date:
    return date.today()


def register_flake(
    registry: list[GraveEntry], test_name: str, *, owner: str = "",
    ticket_url: str = "", today: date | None = None,
) -> GraveEntry:
    """Insert / update an entry. Returns the affected entry."""
    if not isinstance(registry, list):
        raise FlakinessGraveyardError("registry must be a list")
    today = today or _today()
    today_iso = today.isoformat()
    for entry in registry:
        if entry.test_name == test_name:
            entry.last_flake_date = today_iso
            if entry.status == Status.REVIVED:
                entry.status = Status.QUARANTINED
                entry.quarantined_at = today_iso
            return entry
    new_entry = GraveEntry(
        test_name=test_name,
        quarantined_at=today_iso,
        last_flake_date=today_iso,
        owner=owner,
        ticket_url=ticket_url,
    )
    registry.append(new_entry)
    return new_entry


def revive(registry: list[GraveEntry], test_name: str) -> GraveEntry:
    for entry in registry:
        if entry.test_name == test_name:
            if entry.status == Status.BURIED:
                raise FlakinessGraveyardError(
                    f"{test_name!r} already buried — cannot revive from grave"
                )
            entry.status = Status.REVIVED
            return entry
    raise FlakinessGraveyardError(f"unknown test {test_name!r}")


def due_for_burial(
    registry: Iterable[GraveEntry],
    *, days: int = 30, today: date | None = None,
) -> list[GraveEntry]:
    """Quarantined tests untouched for >= ``days`` days."""
    if days < 1:
        raise FlakinessGraveyardError("days must be >= 1")
    today = today or _today()
    out: list[GraveEntry] = []
    for entry in registry:
        if entry.status != Status.QUARANTINED:
            continue
        last = _parse_date(entry.last_flake_date, "last_flake_date")
        if (today - last) >= timedelta(days=days):
            out.append(entry)
    return out


def bury(registry: list[GraveEntry], test_name: str) -> GraveEntry:
    for entry in registry:
        if entry.test_name == test_name:
            if entry.status != Status.QUARANTINED:
                raise FlakinessGraveyardError(
                    f"cannot bury {test_name!r}: status={entry.status.value}"
                )
            entry.status = Status.BURIED
            return entry
    raise FlakinessGraveyardError(f"unknown test {test_name!r}")


def load(path: str) -> list[GraveEntry]:
    if not isinstance(path, str) or not path:
        raise FlakinessGraveyardError("path must be non-empty string")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    if not isinstance(raw, list):
        raise FlakinessGraveyardError(
            f"registry file {path!r} must contain a JSON array"
        )
    out: list[GraveEntry] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        out.append(GraveEntry(
            test_name=item.get("test_name", ""),
            quarantined_at=item.get("quarantined_at", _today().isoformat()),
            last_flake_date=item.get("last_flake_date", _today().isoformat()),
            owner=item.get("owner", ""),
            ticket_url=item.get("ticket_url", ""),
            status=Status(item.get("status", Status.QUARANTINED.value)),
        ))
    return out


def save(path: str, registry: Iterable[GraveEntry]) -> None:
    if not isinstance(path, str) or not path:
        raise FlakinessGraveyardError("path must be non-empty string")
    serialized = [e.to_dict() for e in registry]
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(serialized, fh, indent=2)
