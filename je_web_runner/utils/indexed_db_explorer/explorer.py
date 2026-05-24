"""
IndexedDB 內容快照 + 物件 / store / index 斷言。
PWA、離線優先的 app、Firebase / Dexie / RxDB 都把狀態放在 IndexedDB。
傳統 Selenium 測試只看 DOM,根本看不到資料層;這個模組:

* 提供瀏覽器端 JS snippet,把指定 DB 的內容序列化成可帶回的 JSON
  (透過 CDP ``Runtime.evaluate`` 或 Playwright ``page.evaluate``)
* 解析 JSON snapshot 成 :class:`IdbSnapshot`,提供 store / key / index
  / 紀錄計數的斷言

不直接操作 driver — JS 給你,evaluate 你自己叫。
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException


class IndexedDbExplorerError(WebRunnerException):
    """Raised on malformed snapshot input or failed assertion."""


# ---------- harvest script ---------------------------------------------

_HARVEST_TEMPLATE = """
(async function() {
  const dbName = %(db_name)s;
  if (!('indexedDB' in window)) {
    return {schema_version: 1, name: dbName, exists: false, stores: {}};
  }
  return await new Promise(function(resolve, reject) {
    const req = indexedDB.open(dbName);
    req.onerror = function() { reject(new Error('open failed: ' + req.error)); };
    req.onsuccess = async function() {
      const db = req.result;
      const out = {
        schema_version: 1, name: db.name, exists: true,
        version: db.version,
        stores: {}
      };
      const tx = db.transaction(Array.from(db.objectStoreNames), 'readonly');
      for (const sname of db.objectStoreNames) {
        const store = tx.objectStore(sname);
        const records = await new Promise(function(r2) {
          const all = store.getAll();
          all.onsuccess = function() { r2(all.result); };
          all.onerror = function() { r2([]); };
        });
        const keys = await new Promise(function(r3) {
          const all = store.getAllKeys();
          all.onsuccess = function() { r3(all.result); };
          all.onerror = function() { r3([]); };
        });
        out.stores[sname] = {
          key_path: store.keyPath,
          auto_increment: store.autoIncrement,
          index_names: Array.from(store.indexNames),
          records: records,
          keys: keys
        };
      }
      db.close();
      resolve(out);
    };
  });
})()
""".strip()


def build_harvest_script(db_name: str) -> str:
    """Return JS that resolves with the snapshot JSON for ``db_name``."""
    if not isinstance(db_name, str) or not db_name:
        raise IndexedDbExplorerError("db_name must be non-empty string")
    return _HARVEST_TEMPLATE % {"db_name": json.dumps(db_name)}


# ---------- snapshot model ---------------------------------------------

@dataclass
class StoreSnapshot:
    """One object-store snapshot."""

    name: str
    key_path: Any = None
    auto_increment: bool = False
    index_names: List[str] = field(default_factory=list)
    records: List[Any] = field(default_factory=list)
    keys: List[Any] = field(default_factory=list)

    def find_one(self, predicate: Callable[[Any], bool]) -> Optional[Any]:
        for r in self.records:
            try:
                if predicate(r):
                    return r
            except Exception:  # nosec B112 — user predicate may legitimately raise; skip + continue
                continue
        return None


@dataclass
class IdbSnapshot:
    """Full DB snapshot."""

    name: str
    exists: bool
    version: Optional[int] = None
    stores: Dict[str, StoreSnapshot] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IdbSnapshot":
        if not isinstance(data, dict):
            raise IndexedDbExplorerError(
                f"snapshot must be dict, got {type(data).__name__}"
            )
        if "stores" in data and not isinstance(data["stores"], dict):
            raise IndexedDbExplorerError("snapshot.stores must be a dict")
        stores: Dict[str, StoreSnapshot] = {}
        for name, raw in (data.get("stores") or {}).items():
            if not isinstance(raw, dict):
                continue
            stores[str(name)] = StoreSnapshot(
                name=str(name),
                key_path=raw.get("key_path"),
                auto_increment=bool(raw.get("auto_increment", False)),
                index_names=[str(i) for i in raw.get("index_names") or []],
                records=list(raw.get("records") or []),
                keys=list(raw.get("keys") or []),
            )
        return cls(
            name=str(data.get("name") or ""),
            exists=bool(data.get("exists", False)),
            version=data.get("version"),
            stores=stores,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "exists": self.exists,
            "version": self.version,
            "stores": {k: asdict(v) for k, v in self.stores.items()},
        }


# ---------- assertions --------------------------------------------------

def assert_db_exists(snapshot: IdbSnapshot) -> None:
    if not isinstance(snapshot, IdbSnapshot):
        raise IndexedDbExplorerError("expected IdbSnapshot")
    if not snapshot.exists:
        raise IndexedDbExplorerError(f"IndexedDB {snapshot.name!r} does not exist")


def assert_store_present(snapshot: IdbSnapshot, store_name: str) -> StoreSnapshot:
    if not isinstance(store_name, str) or not store_name:
        raise IndexedDbExplorerError("store_name must be a non-empty string")
    store = snapshot.stores.get(store_name)
    if store is None:
        existing = sorted(snapshot.stores)
        raise IndexedDbExplorerError(
            f"store {store_name!r} not in snapshot; existing: {existing}"
        )
    return store


def assert_record_count(
    snapshot: IdbSnapshot,
    store_name: str,
    *,
    minimum: int = 0,
    maximum: Optional[int] = None,
) -> int:
    """Assert ``minimum <= len(records) <= maximum``."""
    if minimum < 0:
        raise IndexedDbExplorerError("minimum must be >= 0")
    if maximum is not None and maximum < minimum:
        raise IndexedDbExplorerError("maximum must be >= minimum")
    store = assert_store_present(snapshot, store_name)
    count = len(store.records)
    if count < minimum or (maximum is not None and count > maximum):
        raise IndexedDbExplorerError(
            f"store {store_name!r} has {count} records, want "
            f"[{minimum}, {maximum if maximum is not None else 'inf'}]"
        )
    return count


def assert_key_present(snapshot: IdbSnapshot, store_name: str, key: Any) -> None:
    store = assert_store_present(snapshot, store_name)
    if key not in store.keys:
        raise IndexedDbExplorerError(
            f"key {key!r} not present in store {store_name!r}"
        )


def assert_record_matching(
    snapshot: IdbSnapshot,
    store_name: str,
    predicate: Callable[[Any], bool],
    *,
    description: str = "predicate",
) -> Any:
    """Assert at least one record satisfies ``predicate``; return it."""
    store = assert_store_present(snapshot, store_name)
    found = store.find_one(predicate)
    if found is None:
        raise IndexedDbExplorerError(
            f"no record in {store_name!r} matched: {description}"
        )
    return found


def assert_index_present(
    snapshot: IdbSnapshot, store_name: str, index_name: str,
) -> None:
    store = assert_store_present(snapshot, store_name)
    if index_name not in store.index_names:
        raise IndexedDbExplorerError(
            f"index {index_name!r} not on store {store_name!r}; "
            f"existing: {sorted(store.index_names)}"
        )


# ---------- diff --------------------------------------------------------

@dataclass
class SnapshotDiff:
    """High-level diff between two snapshots."""

    added_stores: List[str] = field(default_factory=list)
    removed_stores: List[str] = field(default_factory=list)
    record_count_changes: Dict[str, Dict[str, int]] = field(default_factory=dict)


def diff_snapshots(before: IdbSnapshot, after: IdbSnapshot) -> SnapshotDiff:
    """Compute a coarse diff (added / removed stores, per-store count delta)."""
    if not isinstance(before, IdbSnapshot) or not isinstance(after, IdbSnapshot):
        raise IndexedDbExplorerError("both arguments must be IdbSnapshot")
    diff = SnapshotDiff()
    before_names = set(before.stores)
    after_names = set(after.stores)
    diff.added_stores = sorted(after_names - before_names)
    diff.removed_stores = sorted(before_names - after_names)
    for name in sorted(before_names & after_names):
        a = len(before.stores[name].records)
        b = len(after.stores[name].records)
        if a != b:
            diff.record_count_changes[name] = {"before": a, "after": b}
    return diff
