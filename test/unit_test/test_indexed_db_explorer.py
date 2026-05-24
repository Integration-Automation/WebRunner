"""Unit tests for je_web_runner.utils.indexed_db_explorer."""
import unittest

from je_web_runner.utils.indexed_db_explorer.explorer import (
    IdbSnapshot,
    IndexedDbExplorerError,
    SnapshotDiff,
    StoreSnapshot,
    assert_db_exists,
    assert_index_present,
    assert_key_present,
    assert_record_count,
    assert_record_matching,
    assert_store_present,
    build_harvest_script,
    diff_snapshots,
)


def _snap_dict(stores=None, exists=True, name="myDb", version=1):
    return {
        "name": name, "exists": exists, "version": version,
        "stores": stores or {},
    }


def _store(records, keys=None, indexes=None):
    return {
        "key_path": "id", "auto_increment": False,
        "index_names": list(indexes or []),
        "records": list(records),
        "keys": list(keys or [r.get("id") for r in records]),
    }


class TestHarvestScript(unittest.TestCase):

    def test_embeds_db_name(self):
        js = build_harvest_script("MyApp")
        self.assertIn('"MyApp"', js)
        self.assertIn("indexedDB.open", js)

    def test_rejects_empty_name(self):
        with self.assertRaises(IndexedDbExplorerError):
            build_harvest_script("")


class TestSnapshotParse(unittest.TestCase):

    def test_basic(self):
        snap = IdbSnapshot.from_dict(_snap_dict({
            "users": _store([{"id": 1, "name": "alice"}]),
        }))
        self.assertTrue(snap.exists)
        self.assertEqual(snap.version, 1)
        self.assertIn("users", snap.stores)
        self.assertEqual(snap.stores["users"].records[0]["name"], "alice")

    def test_missing_db(self):
        snap = IdbSnapshot.from_dict({"name": "x", "exists": False})
        self.assertFalse(snap.exists)
        self.assertEqual(snap.stores, {})

    def test_rejects_non_dict(self):
        with self.assertRaises(IndexedDbExplorerError):
            IdbSnapshot.from_dict("nope")  # type: ignore[arg-type]

    def test_rejects_bad_stores(self):
        with self.assertRaises(IndexedDbExplorerError):
            IdbSnapshot.from_dict({"stores": "not a dict"})

    def test_ignores_bad_store_entries(self):
        snap = IdbSnapshot.from_dict({"stores": {"x": "not a dict"}})
        self.assertEqual(snap.stores, {})

    def test_round_trip_dict(self):
        snap = IdbSnapshot.from_dict(_snap_dict({"u": _store([])}))
        data = snap.to_dict()
        self.assertEqual(data["name"], "myDb")
        self.assertIn("u", data["stores"])


class TestAssertions(unittest.TestCase):

    def _snap(self):
        return IdbSnapshot.from_dict(_snap_dict({
            "users": _store(
                [{"id": 1, "name": "alice"}, {"id": 2, "name": "bob"}],
                indexes=["by_name"],
            ),
            "todos": _store([{"id": "a", "done": False}]),
        }))

    def test_db_exists(self):
        assert_db_exists(self._snap())

    def test_db_not_exists(self):
        with self.assertRaises(IndexedDbExplorerError):
            assert_db_exists(IdbSnapshot.from_dict({"exists": False}))

    def test_db_exists_rejects_non_snapshot(self):
        with self.assertRaises(IndexedDbExplorerError):
            assert_db_exists("nope")  # type: ignore[arg-type]

    def test_store_present(self):
        store = assert_store_present(self._snap(), "users")
        self.assertIsInstance(store, StoreSnapshot)

    def test_store_missing(self):
        with self.assertRaises(IndexedDbExplorerError):
            assert_store_present(self._snap(), "missing")

    def test_store_empty_name(self):
        with self.assertRaises(IndexedDbExplorerError):
            assert_store_present(self._snap(), "")

    def test_record_count_in_range(self):
        self.assertEqual(
            assert_record_count(self._snap(), "users", minimum=1, maximum=10), 2,
        )

    def test_record_count_out_of_range(self):
        with self.assertRaises(IndexedDbExplorerError):
            assert_record_count(self._snap(), "users", minimum=5)
        with self.assertRaises(IndexedDbExplorerError):
            assert_record_count(self._snap(), "users", maximum=1)

    def test_record_count_bad_bounds(self):
        with self.assertRaises(IndexedDbExplorerError):
            assert_record_count(self._snap(), "users", minimum=-1)
        with self.assertRaises(IndexedDbExplorerError):
            assert_record_count(self._snap(), "users", minimum=5, maximum=1)

    def test_key_present(self):
        assert_key_present(self._snap(), "users", 1)

    def test_key_missing(self):
        with self.assertRaises(IndexedDbExplorerError):
            assert_key_present(self._snap(), "users", 999)

    def test_record_matching_pass(self):
        record = assert_record_matching(
            self._snap(), "users", lambda r: r["name"] == "bob",
        )
        self.assertEqual(record["id"], 2)

    def test_record_matching_fail(self):
        with self.assertRaises(IndexedDbExplorerError):
            assert_record_matching(self._snap(), "users", lambda r: False)

    def test_record_matching_predicate_error_ignored(self):
        def bad(_):
            raise RuntimeError("oops")
        with self.assertRaises(IndexedDbExplorerError):
            assert_record_matching(self._snap(), "users", bad)

    def test_index_present(self):
        assert_index_present(self._snap(), "users", "by_name")

    def test_index_missing(self):
        with self.assertRaises(IndexedDbExplorerError):
            assert_index_present(self._snap(), "users", "missing")


class TestDiff(unittest.TestCase):

    def test_added_removed_changed(self):
        before = IdbSnapshot.from_dict(_snap_dict({
            "a": _store([{"id": 1}]),
            "b": _store([]),
        }))
        after = IdbSnapshot.from_dict(_snap_dict({
            "a": _store([{"id": 1}, {"id": 2}]),
            "c": _store([]),
        }))
        diff = diff_snapshots(before, after)
        self.assertEqual(diff.added_stores, ["c"])
        self.assertEqual(diff.removed_stores, ["b"])
        self.assertEqual(diff.record_count_changes,
                         {"a": {"before": 1, "after": 2}})

    def test_rejects_non_snapshot(self):
        with self.assertRaises(IndexedDbExplorerError):
            diff_snapshots("a", "b")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
