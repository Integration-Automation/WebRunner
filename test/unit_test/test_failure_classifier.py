import os
import tempfile
import unittest

from je_web_runner.utils.run_ledger.classifier import (
    classify,
    classify_error,
    classify_failures,
)
from je_web_runner.utils.run_ledger.ledger import record_run


class TestClassifyError(unittest.TestCase):

    def test_transient_patterns(self):
        for repr_str in (
            "selenium.common.exceptions.WebDriverException(...)",
            "ConnectionRefusedError",
            "TimeoutError: timed out",
            "Stale Element Reference",
            "HTTP 503 Service Unavailable",
        ):
            self.assertEqual(classify_error(repr_str), "transient")

    def test_environment_patterns(self):
        for repr_str in (
            "OSError: ENOSPC",
            "MemoryError",
            "chromedriver not found in PATH",
            "DNS lookup failed",
        ):
            self.assertEqual(classify_error(repr_str), "environment")

    def test_unknown_returns_none(self):
        self.assertIsNone(classify_error("AssertionError: 1 != 2"))


class TestClassify(unittest.TestCase):

    def test_real_when_no_pattern_and_no_history(self):
        self.assertEqual(classify("AssertionError: nope"), "real")

    def test_flaky_when_path_in_history(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = os.path.join(tmpdir, "ledger.json")
            record_run(ledger, "wobble.json", True)
            record_run(ledger, "wobble.json", False)
            record_run(ledger, "wobble.json", True)
            self.assertEqual(
                classify("AssertionError: wobble", ledger_path=ledger, file_path="wobble.json"),
                "flaky",
            )

    def test_transient_takes_precedence_over_flaky(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = os.path.join(tmpdir, "ledger.json")
            record_run(ledger, "wobble.json", True)
            record_run(ledger, "wobble.json", False)
            record_run(ledger, "wobble.json", True)
            self.assertEqual(
                classify("TimeoutError: x", ledger_path=ledger, file_path="wobble.json"),
                "transient",
            )


class TestClassifyFailures(unittest.TestCase):

    def test_returns_dict_keyed_by_path(self):
        failures = [
            {"file_path": "a.json", "exception": "AssertionError"},
            {"file_path": "b.json", "exception": "TimeoutError"},
        ]
        result = classify_failures(failures)
        self.assertEqual(result["a.json"], "real")
        self.assertEqual(result["b.json"], "transient")


if __name__ == "__main__":
    unittest.main()
