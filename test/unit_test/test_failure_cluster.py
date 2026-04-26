import unittest

from je_web_runner.utils.failure_cluster import (
    FailureClusterError,
    cluster_failures,
    normalise_error,
)
from je_web_runner.utils.failure_cluster.clustering import cluster_summary


class TestNormaliseError(unittest.TestCase):

    def test_strips_hex_addresses(self):
        result = normalise_error("ElementNotInteractable at 0xdeadbeef")
        self.assertNotIn("0xdeadbeef", result)
        self.assertIn("<hex>", result)

    def test_strips_line_numbers(self):
        result = normalise_error("Traceback line 42 in foo")
        self.assertIn("line <n>", result)

    def test_strips_paths(self):
        result = normalise_error("File /home/x/y/z.py failed")
        self.assertIn("<path>", result)
        self.assertNotIn("/home/", result)

    def test_strips_quoted_strings(self):
        result = normalise_error('Element "submit-button-32f12" missing')
        self.assertIn("<q>", result)

    def test_lowercases(self):
        self.assertEqual(normalise_error("TIMEOUT").startswith("timeout"), True)


class TestClusterFailures(unittest.TestCase):

    def test_groups_same_signature(self):
        failures = [
            {"function_name": "a", "exception": "TimeoutError at 0xabc"},
            {"function_name": "b", "exception": "TimeoutError at 0xdef"},
            {"function_name": "c", "exception": "ValueError: bad input"},
        ]
        clusters = cluster_failures(failures)
        self.assertEqual(len(clusters), 2)
        self.assertEqual(clusters[0].count, 2)

    def test_files_collected_per_cluster(self):
        failures = [
            {"function_name": "x", "exception": "TimeoutError",
             "file_path": "actions/login.json"},
            {"function_name": "y", "exception": "TimeoutError",
             "file_path": "actions/cart.json"},
        ]
        clusters = cluster_failures(failures)
        self.assertEqual(len(clusters), 1)
        self.assertEqual(set(clusters[0].files),
                         {"actions/login.json", "actions/cart.json"})

    def test_top_n_truncation(self):
        failures = [
            {"function_name": "a", "exception": "Err1"},
            {"function_name": "a", "exception": "Err1"},
            {"function_name": "b", "exception": "Err2"},
            {"function_name": "c", "exception": "Err3"},
        ]
        clusters = cluster_failures(failures, top_n=2)
        self.assertEqual(len(clusters), 2)
        self.assertEqual(clusters[0].count, 2)

    def test_empty_input(self):
        self.assertEqual(cluster_failures([]), [])

    def test_invalid_entry_type(self):
        with self.assertRaises(FailureClusterError):
            cluster_failures(["not a dict"])  # type: ignore[arg-type]

    def test_unknown_signature_grouped(self):
        clusters = cluster_failures([
            {"function_name": "a", "exception": ""},
            {"function_name": "b"},
        ])
        self.assertEqual(len(clusters), 1)
        self.assertEqual(clusters[0].signature, "<unknown>")


class TestClusterSummary(unittest.TestCase):

    def test_summary_shape(self):
        failures = [
            {"function_name": "x", "exception": "TimeoutError",
             "file_path": "actions/login.json"},
        ]
        clusters = cluster_failures(failures)
        summary = cluster_summary(clusters)
        self.assertEqual(summary[0]["count"], 1)
        self.assertEqual(summary[0]["files"], ["actions/login.json"])
        self.assertIn("TimeoutError", summary[0]["representative"])


if __name__ == "__main__":
    unittest.main()
