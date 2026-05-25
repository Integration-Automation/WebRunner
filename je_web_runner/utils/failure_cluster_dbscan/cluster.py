"""
Failure-message clustering for root-cause grouping.

When a regression breaks 200 tests, you don't want 200 Jira tickets —
you want one ticket per *cause*. This module:

* Tokenises failure messages with the obvious noise stripped (line
  numbers, hex addresses, GUIDs, timestamps, tmp paths).
* Computes pairwise Jaccard distance over token sets.
* Runs a small DBSCAN clustering (pure Python, no sklearn) to group
  near-identical messages.
* Emits a ``Cluster`` per cause with representative message + count.

No numpy / sklearn dependency.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

from je_web_runner.utils.exception.exceptions import WebRunnerException


class FailureClusterDbscanError(WebRunnerException):
    """Raised on malformed input."""


@dataclass
class FailureRecord:
    test_name: str
    message: str


_NOISE_PATTERNS = (
    re.compile(r"\b0x[0-9a-fA-F]+\b"),                  # hex addresses
    re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-"
               r"[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
               r"[0-9a-fA-F]{12}\b"),                   # GUIDs
    re.compile(r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}\S*"),  # ISO ts
    re.compile(r"\b\d+\b"),                              # bare numbers
    re.compile(r"/tmp/[^\s]+"),                          # tmp paths
    re.compile(r"\\[A-Za-z]+\\[^\s]+"),                  # Windows paths
)


def _tokenize(message: str) -> Set[str]:
    if not isinstance(message, str):
        return set()
    cleaned = message
    for p in _NOISE_PATTERNS:
        cleaned = p.sub(" ", cleaned)
    return {t.lower() for t in re.findall(r"\w{3,}", cleaned)}


def _jaccard_distance(a: Set[str], b: Set[str]) -> float:
    if not a and not b:
        return 0.0
    union = a | b
    if not union:
        return 1.0
    inter = a & b
    return 1.0 - len(inter) / len(union)


@dataclass
class Cluster:
    representative: str
    members: List[str] = field(default_factory=list)

    @property
    def size(self) -> int:
        return len(self.members)


def cluster(
    records: Sequence[FailureRecord], *,
    eps: float = 0.3, min_samples: int = 2,
) -> List[Cluster]:
    """Tiny DBSCAN. Returns one ``Cluster`` per dense group. Noise points
    become singleton clusters."""
    if not 0 < eps <= 1:
        raise FailureClusterDbscanError("eps must be in (0, 1]")
    if min_samples < 1:
        raise FailureClusterDbscanError("min_samples must be >= 1")
    if not isinstance(records, (list, tuple)):
        raise FailureClusterDbscanError("records must be a sequence")
    tokens = [_tokenize(r.message) for r in records]
    n = len(records)
    labels: List[Optional[int]] = [None] * n
    cluster_id = 0

    def neighbours(i: int) -> List[int]:
        return [j for j in range(n)
                if j != i
                and _jaccard_distance(tokens[i], tokens[j]) <= eps]

    for i in range(n):
        if labels[i] is not None:
            continue
        nbs = neighbours(i)
        if len(nbs) < min_samples - 1:
            labels[i] = -1
            continue
        labels[i] = cluster_id
        queue = list(nbs)
        while queue:
            j = queue.pop(0)
            if labels[j] == -1:
                labels[j] = cluster_id
            elif labels[j] is None:
                labels[j] = cluster_id
                inner = neighbours(j)
                if len(inner) >= min_samples - 1:
                    queue.extend(k for k in inner
                                 if labels[k] in (None, -1))
        cluster_id += 1

    buckets: Dict[int, List[int]] = defaultdict(list)
    for i, label in enumerate(labels):
        buckets[label if label is not None else -1].append(i)

    clusters: List[Cluster] = []
    next_singleton_label = max(buckets) + 1 if buckets else 0
    for label, indexes in buckets.items():
        if label == -1:
            for i in indexes:
                clusters.append(Cluster(
                    representative=records[i].message,
                    members=[records[i].test_name],
                ))
        else:
            rep_index = indexes[0]
            clusters.append(Cluster(
                representative=records[rep_index].message,
                members=[records[i].test_name for i in indexes],
            ))
    return sorted(clusters, key=lambda c: -c.size)


def cluster_summary(clusters: Iterable[Cluster]) -> List[Dict[str, Any]]:
    return [{"representative": c.representative[:120],
             "size": c.size,
             "tests": c.members[:5]} for c in clusters]


def assert_root_causes_at_most(
    clusters: Iterable[Cluster], *, max_clusters: int,
) -> None:
    """If we expect a single underlying cause behind many failures,
    cluster count should stay below a sensible threshold."""
    if max_clusters < 1:
        raise FailureClusterDbscanError("max_clusters must be >= 1")
    items = [c for c in clusters if c.size >= 2]
    if len(items) > max_clusters:
        raise FailureClusterDbscanError(
            f"found {len(items)} non-singleton failure clusters, "
            f"expected <= {max_clusters}"
        )
