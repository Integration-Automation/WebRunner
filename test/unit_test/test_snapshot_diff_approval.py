"""Unit tests for je_web_runner.utils.snapshot_diff_approval."""
import json
import os
import tempfile
import unittest

from je_web_runner.utils.snapshot_diff_approval.approval import (
    SnapshotDiffApprovalError,
    SnapshotEntry,
    Status,
    approve,
    assert_no_pending,
    capture,
    list_pending,
    load,
    reject,
    save,
)


class TestCapture(unittest.TestCase):

    def test_first_time_pending(self):
        reg = {}
        result = capture(reg, name="hero", payload=b"abc")
        self.assertEqual(reg["hero"].status, Status.PENDING)
        self.assertEqual(result.baseline_sha, "")

    def test_match_baseline(self):
        reg = {"hero": SnapshotEntry(name="hero", sha256="x",
                                     status=Status.BASELINE,
                                     updated_at="2026-01-01")}
        # craft a payload whose sha matches "x" — we'll instead use a fresh
        # baseline produced by capture+approve.
        reg2 = {}
        capture(reg2, name="hero", payload=b"abc")
        approve(reg2, name="hero", reviewer="alice")
        result = capture(reg2, name="hero", payload=b"abc")
        self.assertFalse(result.changed)

    def test_diff_pending(self):
        reg = {}
        capture(reg, name="hero", payload=b"abc")
        approve(reg, name="hero", reviewer="alice")
        result = capture(reg, name="hero", payload=b"xyz")
        self.assertTrue(result.changed)
        self.assertEqual(reg["hero"].status, Status.PENDING)

    def test_bad_payload(self):
        with self.assertRaises(SnapshotDiffApprovalError):
            capture({}, name="x", payload="nope")

    def test_empty_name(self):
        with self.assertRaises(SnapshotDiffApprovalError):
            capture({}, name="", payload=b"x")


class TestApprove(unittest.TestCase):

    def test_pass(self):
        reg = {}
        capture(reg, name="hero", payload=b"abc")
        entry = approve(reg, name="hero", reviewer="alice")
        self.assertEqual(entry.status, Status.BASELINE)

    def test_unknown(self):
        with self.assertRaises(SnapshotDiffApprovalError):
            approve({}, name="missing", reviewer="x")

    def test_not_pending(self):
        reg = {"hero": SnapshotEntry(name="hero", sha256="x",
                                     status=Status.BASELINE,
                                     updated_at="2026-01-01")}
        with self.assertRaises(SnapshotDiffApprovalError):
            approve(reg, name="hero", reviewer="alice")

    def test_no_reviewer(self):
        reg = {}
        capture(reg, name="x", payload=b"x")
        with self.assertRaises(SnapshotDiffApprovalError):
            approve(reg, name="x", reviewer="")


class TestReject(unittest.TestCase):

    def test_pass(self):
        reg = {}
        capture(reg, name="x", payload=b"x")
        entry = reject(reg, name="x", reviewer="alice", note="ugly")
        self.assertEqual(entry.status, Status.REJECTED)
        self.assertEqual(entry.note, "ugly")

    def test_unknown(self):
        with self.assertRaises(SnapshotDiffApprovalError):
            reject({}, name="x", reviewer="alice")

    def test_no_reviewer(self):
        reg = {}
        capture(reg, name="x", payload=b"x")
        with self.assertRaises(SnapshotDiffApprovalError):
            reject(reg, name="x", reviewer="")


class TestList(unittest.TestCase):

    def test_pending(self):
        reg = {}
        capture(reg, name="a", payload=b"x")
        self.assertEqual(len(list_pending(reg)), 1)


class TestAssert(unittest.TestCase):

    def test_pass(self):
        assert_no_pending({})

    def test_fail(self):
        reg = {}
        capture(reg, name="a", payload=b"x")
        with self.assertRaises(SnapshotDiffApprovalError):
            assert_no_pending(reg)


class TestSaveLoad(unittest.TestCase):

    def test_roundtrip(self):
        reg = {}
        capture(reg, name="hero", payload=b"x")
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "s.json")
            save(path, reg)
            loaded = load(path)
            self.assertIn("hero", loaded)

    def test_load_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(load(os.path.join(tmp, "x.json")), {})

    def test_save_empty_path(self):
        with self.assertRaises(SnapshotDiffApprovalError):
            save("", {})

    def test_load_bad_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "s.json")
            with open(path, "w") as fh:
                json.dump([], fh)
            with self.assertRaises(SnapshotDiffApprovalError):
                load(path)


if __name__ == "__main__":
    unittest.main()
