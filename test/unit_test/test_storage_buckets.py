"""Unit tests for je_web_runner.utils.storage_buckets."""
import unittest

from je_web_runner.utils.storage_buckets.buckets import (
    BucketSnapshot,
    BucketsReport,
    HARVEST_SCRIPT,
    StorageBucketsError,
    assert_bucket_present,
    assert_durability,
    assert_idb_isolated,
    assert_no_unexpected_buckets,
    assert_supported,
    parse_snapshot,
)


def _payload(*buckets, supported=True):
    return {"supported": supported, "buckets": list(buckets)}


def _b(name, **kwargs):
    return {"name": name, **kwargs}


class TestHarvestScript(unittest.TestCase):

    def test_uses_api(self):
        self.assertIn("navigator.storageBuckets", HARVEST_SCRIPT)


class TestParse(unittest.TestCase):

    def test_basic(self):
        rep = parse_snapshot(_payload(
            _b("default", idb_databases=["app"], durability="strict"),
        ))
        self.assertTrue(rep.supported)
        self.assertEqual(rep.buckets[0].durability, "strict")

    def test_unsupported(self):
        self.assertFalse(parse_snapshot({"supported": False, "buckets": []}).supported)

    def test_skips_nameless(self):
        rep = parse_snapshot(_payload({"durability": "strict"}))
        self.assertEqual(rep.buckets, [])

    def test_rejects_non_dict(self):
        with self.assertRaises(StorageBucketsError):
            parse_snapshot("nope")

    def test_rejects_bad_buckets(self):
        with self.assertRaises(StorageBucketsError):
            parse_snapshot({"supported": True, "buckets": "x"})


class TestAssertions(unittest.TestCase):

    def _rep(self):
        return parse_snapshot(_payload(
            _b("default", idb_databases=["app"], durability="strict"),
            _b("inbox", idb_databases=["messages"], durability="relaxed"),
        ))

    def test_supported_pass(self):
        assert_supported(self._rep())

    def test_supported_fail(self):
        with self.assertRaises(StorageBucketsError):
            assert_supported(parse_snapshot({"supported": False, "buckets": []}))

    def test_bucket_present(self):
        assert_bucket_present(self._rep(), name="default")

    def test_bucket_missing(self):
        with self.assertRaises(StorageBucketsError):
            assert_bucket_present(self._rep(), name="other")

    def test_bucket_empty_name(self):
        with self.assertRaises(StorageBucketsError):
            assert_bucket_present(self._rep(), name="")

    def test_isolated_pass(self):
        assert_idb_isolated(self._rep(), db_name="app", expected_bucket="default")

    def test_isolated_leak(self):
        rep = parse_snapshot(_payload(
            _b("a", idb_databases=["shared"]),
            _b("b", idb_databases=["shared"]),
        ))
        with self.assertRaises(StorageBucketsError):
            assert_idb_isolated(rep, db_name="shared", expected_bucket="a")

    def test_isolated_missing(self):
        with self.assertRaises(StorageBucketsError):
            assert_idb_isolated(self._rep(), db_name="ghost", expected_bucket="default")

    def test_durability_pass(self):
        assert_durability(self._rep(), name="default", expected="strict")

    def test_durability_fail(self):
        with self.assertRaises(StorageBucketsError):
            assert_durability(self._rep(), name="default", expected="relaxed")

    def test_durability_bad_arg(self):
        with self.assertRaises(StorageBucketsError):
            assert_durability(self._rep(), name="default", expected="weird")

    def test_no_unexpected_pass(self):
        assert_no_unexpected_buckets(self._rep(), allowed=["default", "inbox"])

    def test_no_unexpected_fail(self):
        with self.assertRaises(StorageBucketsError):
            assert_no_unexpected_buckets(self._rep(), allowed=["default"])


class TestByName(unittest.TestCase):

    def test_dict(self):
        rep = BucketsReport(supported=True, buckets=[
            BucketSnapshot(name="x"),
        ])
        self.assertIn("x", rep.by_name())


if __name__ == "__main__":
    unittest.main()
