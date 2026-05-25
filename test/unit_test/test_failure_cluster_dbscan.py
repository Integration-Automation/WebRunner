"""Unit tests for je_web_runner.utils.failure_cluster_dbscan."""
import unittest

from je_web_runner.utils.failure_cluster_dbscan.cluster import (
    Cluster,
    FailureClusterDbscanError,
    FailureRecord,
    assert_root_causes_at_most,
    cluster,
    cluster_summary,
)


class TestCluster(unittest.TestCase):

    def test_groups_similar(self):
        records = [
            FailureRecord("t1", "TimeoutException waiting for element #foo"),
            FailureRecord("t2", "TimeoutException waiting for element #bar"),
            FailureRecord("t3", "TimeoutException waiting for element #baz"),
        ]
        clusters = cluster(records, eps=0.5, min_samples=2)
        self.assertEqual(clusters[0].size, 3)

    def test_separates_distinct(self):
        records = [
            FailureRecord("t1", "TimeoutException waiting for foo"),
            FailureRecord("t2", "NoSuchElement: foo"),
        ]
        clusters = cluster(records, eps=0.2, min_samples=2)
        self.assertEqual(len(clusters), 2)

    def test_strips_noise(self):
        records = [
            FailureRecord("t1", "Error at line 123 with 0xdeadbeef"),
            FailureRecord("t2", "Error at line 456 with 0xcafebabe"),
        ]
        clusters = cluster(records, eps=0.2, min_samples=2)
        self.assertEqual(clusters[0].size, 2)

    def test_bad_eps(self):
        with self.assertRaises(FailureClusterDbscanError):
            cluster([], eps=2)

    def test_bad_min_samples(self):
        with self.assertRaises(FailureClusterDbscanError):
            cluster([], min_samples=0)

    def test_bad_records(self):
        with self.assertRaises(FailureClusterDbscanError):
            cluster("nope")


class TestSummary(unittest.TestCase):

    def test_basic(self):
        summary = cluster_summary([Cluster(representative="hi",
                                           members=["a", "b"])])
        self.assertEqual(summary[0]["size"], 2)


class TestAssert(unittest.TestCase):

    def test_pass(self):
        assert_root_causes_at_most(
            [Cluster(representative="x", members=["a", "b"])],
            max_clusters=1,
        )

    def test_fail(self):
        with self.assertRaises(FailureClusterDbscanError):
            assert_root_causes_at_most(
                [Cluster(representative="x", members=["a", "b"]),
                 Cluster(representative="y", members=["c", "d"])],
                max_clusters=1,
            )

    def test_singletons_ignored(self):
        assert_root_causes_at_most(
            [Cluster(representative="x", members=["a"])] * 10,
            max_clusters=1,
        )

    def test_bad_max(self):
        with self.assertRaises(FailureClusterDbscanError):
            assert_root_causes_at_most([], max_clusters=0)


if __name__ == "__main__":
    unittest.main()
