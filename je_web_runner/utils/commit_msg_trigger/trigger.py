"""
Commit-message trigger parser & dispatcher.

Lets engineers steer CI from a commit message. Conventions supported:

* ``[skip ci]`` — skip everything.
* ``[ci e2e]`` — run only the named test job.
* ``[ci shard=3/8]`` — run a specific shard.
* ``[smoke]`` — run a labelled bucket.
* ``Closes #123 / Fixes JIRA-456`` — extract linked tickets.

The module is intentionally CI-system agnostic: it parses the message
into a ``TriggerPlan`` and lets the caller apply the plan.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from je_web_runner.utils.exception.exceptions import WebRunnerException


class CommitMsgTriggerError(WebRunnerException):
    """Raised on malformed messages or downstream dispatch failure."""


_SKIP_RE = re.compile(
    r"\[\s*(?:skip|no)[\s\-_]?ci\s*\]|\[\s*ci[\s\-_]?skip\s*\]",
    re.IGNORECASE,
)
_BUCKET_RE = re.compile(r"\[\s*ci\s+([\w\-:.]+)\s*\]", re.IGNORECASE)
_SHARD_RE = re.compile(
    r"\[\s*ci\s+shard\s*=\s*(\d+)\s*/\s*(\d+)\s*\]",
    re.IGNORECASE,
)
_LABEL_RE = re.compile(r"\[\s*(smoke|nightly|long|gpu|mobile)\s*\]", re.IGNORECASE)

# Bucket name reserved for "do not run any CI"; called out as a constant
# so Bandit's hardcoded-password heuristic doesn't flag the literal.
_SKIP_TOKEN = "skip"  # nosec B105
_TICKET_RE = re.compile(
    r"\b(?:close[ds]?|fix(?:e[sd])?|resolve[sd]?)\s+"
    r"(#\d+|[A-Z]{2,}-\d+)",
    re.IGNORECASE,
)


@dataclass
class TriggerPlan:
    skip: bool = False
    only_buckets: set[str] = field(default_factory=set)
    labels: set[str] = field(default_factory=set)
    shard: tuple[int, int] | None = None
    tickets: set[str] = field(default_factory=set)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["only_buckets"] = sorted(self.only_buckets)
        d["labels"] = sorted(self.labels)
        d["tickets"] = sorted(self.tickets)
        return d


def parse(message: str) -> TriggerPlan:
    if not isinstance(message, str):
        raise CommitMsgTriggerError(
            f"message must be string, got {type(message).__name__}"
        )
    plan = TriggerPlan()
    if _SKIP_RE.search(message):
        plan.skip = True
    for shard in _SHARD_RE.finditer(message):
        idx, total = int(shard.group(1)), int(shard.group(2))
        if total == 0 or idx <= 0 or idx > total:
            raise CommitMsgTriggerError(
                f"invalid shard spec {shard.group(0)!r}"
            )
        plan.shard = (idx, total)
    for bucket in _BUCKET_RE.finditer(message):
        token = bucket.group(1).lower()
        if token == _SKIP_TOKEN:  # nosec B105 - directive name, not a credential
            continue   # [ci skip] already handled by _SKIP_RE
        if token.startswith("shard"):
            continue   # already handled by _SHARD_RE
        plan.only_buckets.add(token)
    for label in _LABEL_RE.finditer(message):
        plan.labels.add(label.group(1).lower())
    for ticket in _TICKET_RE.finditer(message):
        plan.tickets.add(ticket.group(1).upper())
    return plan


def should_run_job(plan: TriggerPlan, job_name: str) -> bool:
    if not job_name:
        raise CommitMsgTriggerError("job_name must be non-empty")
    if plan.skip:
        return False
    if plan.only_buckets and job_name.lower() not in plan.only_buckets:
        return False
    return True


def assigned_shard(plan: TriggerPlan, total_shards: int) -> int | None:
    """If commit overrides shard, return the 0-indexed shard for ``total_shards``.
    Returns None when no override applies."""
    if total_shards <= 0:
        raise CommitMsgTriggerError("total_shards must be positive")
    if plan.shard is None:
        return None
    idx, declared_total = plan.shard
    if declared_total != total_shards:
        raise CommitMsgTriggerError(
            f"commit shard {idx}/{declared_total} doesn't match "
            f"runner total {total_shards}"
        )
    return idx - 1


def assert_no_skip(plan: TriggerPlan) -> None:
    """Useful for protected branches that disallow ``[skip ci]``."""
    if plan.skip:
        raise CommitMsgTriggerError(
            "commit requests [skip ci] but branch policy forbids it"
        )
