"""
Storage Buckets API — partitioned-storage isolation verification。
Storage Buckets (``navigator.storageBuckets``) lets a site split its
IndexedDB / Cache / OPFS storage into named, independently-evictable
silos. The common bug class: code expects bucket A's data when only
bucket B was written. This module:

* Emits the JS to harvest all bucket names + per-bucket store keys.
* Provides a typed snapshot model.
* Asserts: bucket exists, bucket isolated (key not present in other
  buckets), bucket-level quota / durability flags as expected.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class StorageBucketsError(WebRunnerException):
    """Raised on bad snapshot or failed assertion."""


HARVEST_SCRIPT = """
(async function() {
  if (!('storageBuckets' in navigator)) {
    return {supported: false, buckets: []};
  }
  const names = await navigator.storageBuckets.keys();
  const out = [];
  for (const name of names) {
    const bucket = await navigator.storageBuckets.open(name);
    const idbNames = await new Promise(function(resolve) {
      const req = bucket.indexedDB.databases
        ? bucket.indexedDB.databases().then(
            function(list) { resolve(list.map(function(d){return d.name;})); },
            function() { resolve([]); })
        : resolve([]);
    });
    const cacheNames = bucket.caches
      ? await bucket.caches.keys()
      : [];
    let estimate = null;
    if (bucket.estimate) {
      try { estimate = await bucket.estimate(); } catch (e) {}
    }
    out.push({
      name: name,
      idb_databases: idbNames || [],
      cache_names: cacheNames || [],
      durability: bucket.durability || null,
      quota: bucket.quota || null,
      estimate: estimate
    });
  }
  return {supported: true, buckets: out};
})();
""".strip()


# ---------- model -------------------------------------------------------

@dataclass
class BucketSnapshot:
    """One storage bucket's snapshot."""

    name: str
    idb_databases: list[str] = field(default_factory=list)
    cache_names: list[str] = field(default_factory=list)
    durability: str | None = None  # 'strict' / 'relaxed'
    quota: int | None = None
    estimate: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BucketsReport:
    """Full snapshot of all buckets."""

    supported: bool
    buckets: list[BucketSnapshot] = field(default_factory=list)

    def by_name(self) -> dict[str, BucketSnapshot]:
        return {b.name: b for b in self.buckets}


def parse_snapshot(payload: Any) -> BucketsReport:
    if not isinstance(payload, dict):
        raise StorageBucketsError(
            f"snapshot must be dict, got {type(payload).__name__}"
        )
    raw_buckets = payload.get("buckets") or []
    if not isinstance(raw_buckets, list):
        raise StorageBucketsError("buckets must be a list")
    buckets: list[BucketSnapshot] = []
    for raw in raw_buckets:
        if not isinstance(raw, dict) or "name" not in raw:
            continue
        buckets.append(BucketSnapshot(
            name=str(raw["name"]),
            idb_databases=[str(d) for d in raw.get("idb_databases") or []],
            cache_names=[str(c) for c in raw.get("cache_names") or []],
            durability=raw.get("durability"),
            quota=raw.get("quota"),
            estimate=raw.get("estimate"),
        ))
    return BucketsReport(
        supported=bool(payload.get("supported", False)),
        buckets=buckets,
    )


# ---------- assertions --------------------------------------------------

def assert_supported(report: BucketsReport) -> None:
    if not report.supported:
        raise StorageBucketsError("Storage Buckets API not supported in this browser")


def assert_bucket_present(report: BucketsReport, *, name: str) -> BucketSnapshot:
    if not isinstance(name, str) or not name:
        raise StorageBucketsError("name must be non-empty string")
    for bucket in report.buckets:
        if bucket.name == name:
            return bucket
    raise StorageBucketsError(
        f"bucket {name!r} not present (have: {[b.name for b in report.buckets]})"
    )


def assert_idb_isolated(
    report: BucketsReport, *, db_name: str, expected_bucket: str,
) -> None:
    """Assert ``db_name`` lives ONLY in ``expected_bucket``."""
    leaks = [
        b.name for b in report.buckets
        if b.name != expected_bucket and db_name in b.idb_databases
    ]
    if leaks:
        raise StorageBucketsError(
            f"IDB {db_name!r} expected only in {expected_bucket!r}, also found in: {leaks}"
        )
    target = next((b for b in report.buckets if b.name == expected_bucket), None)
    if target is None or db_name not in target.idb_databases:
        raise StorageBucketsError(
            f"IDB {db_name!r} not in expected bucket {expected_bucket!r}"
        )


def assert_durability(
    report: BucketsReport, *, name: str, expected: str,
) -> None:
    if expected not in ("strict", "relaxed"):
        raise StorageBucketsError(
            f"expected must be 'strict' or 'relaxed', got {expected!r}"
        )
    bucket = assert_bucket_present(report, name=name)
    if bucket.durability != expected:
        raise StorageBucketsError(
            f"bucket {name!r} durability is {bucket.durability!r}, want {expected!r}"
        )


def assert_no_unexpected_buckets(
    report: BucketsReport, *, allowed: Sequence[str],
) -> None:
    extras = [b.name for b in report.buckets if b.name not in allowed]
    if extras:
        raise StorageBucketsError(
            f"unexpected buckets present: {extras}"
        )
