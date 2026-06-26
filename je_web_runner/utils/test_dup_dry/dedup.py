"""
Test code DRY-checker.

Detects duplicated test logic across two axes:

* **Action-JSON duplicates** — two WebRunner action JSON files that walk
  the same sequence of action_name + (locator or value) tokens. Shows
  the diff so reviewers know whether to merge or parameterize.
* **Action-prefix overlap** — two files share a long common prefix
  (login → navigate → ...), suggesting an opportunity to extract a
  fixture helper.

The duplicate detection is structural — it ignores formatting and
absolute coordinates so it stays robust across small edits.
"""
from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class DupDryError(WebRunnerException):
    """Raised on malformed input."""


@dataclass
class DupSpec:
    name: str
    actions: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.name:
            raise DupDryError("DupSpec.name required")
        if not isinstance(self.actions, list):
            raise DupDryError("DupSpec.actions must be a list")


def _signature_token(action: Dict[str, Any]) -> str:
    name = (action.get("action_name") or "").lower()
    target = (action.get("element_name") or action.get("by_value")
              or action.get("url") or "")
    return f"{name}:{target}"


def _signature(actions: Sequence[Dict[str, Any]]) -> str:
    joined = "|".join(_signature_token(a) for a in actions if isinstance(a, dict))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]


@dataclass
class DuplicateGroup:
    signature: str
    test_names: List[str]


def find_duplicates(specs: Iterable[DupSpec]) -> List[DuplicateGroup]:
    buckets: Dict[str, List[str]] = defaultdict(list)
    for spec in specs:
        if not isinstance(spec, DupSpec):
            raise DupDryError("each spec must be DupSpec")
        sig = _signature(spec.actions)
        buckets[sig].append(spec.name)
    return [DuplicateGroup(signature=sig, test_names=sorted(names))
            for sig, names in buckets.items() if len(names) >= 2]


@dataclass
class PrefixOverlap:
    a: str
    b: str
    common_prefix_len: int


def _common_prefix(la: List[str], lb: List[str]) -> int:
    n = 0
    for x, y in zip(la, lb, strict=False):
        if x != y:
            break
        n += 1
    return n


def find_prefix_overlap(
    specs: Sequence[DupSpec], *, min_prefix: int = 5,
) -> List[PrefixOverlap]:
    if min_prefix < 1:
        raise DupDryError("min_prefix must be >= 1")
    tokens = {s.name: [_signature_token(a) for a in s.actions
                       if isinstance(a, dict)]
              for s in specs}
    out: List[PrefixOverlap] = []
    names = sorted(tokens)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            la, lb = tokens[a], tokens[b]
            common = _common_prefix(la, lb)
            if common >= min_prefix and common < min(len(la), len(lb)):
                out.append(PrefixOverlap(a=a, b=b, common_prefix_len=common))
    return sorted(out, key=lambda o: -o.common_prefix_len)


def assert_no_duplicates(groups: Iterable[DuplicateGroup]) -> None:
    items = list(groups)
    if items:
        names = [g.test_names for g in items]
        raise DupDryError(
            f"{len(items)} duplicate-action group(s) found: {names}"
        )
