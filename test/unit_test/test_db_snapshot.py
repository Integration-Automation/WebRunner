"""Unit tests for je_web_runner.utils.db_snapshot."""
import unittest

from je_web_runner.utils.db_snapshot.snapshot import (
    DbSnapshotError,
    InMemoryBackend,
    SnapshotHandle,
    SnapshotScope,
    assert_no_active_snapshots,
    pytest_fixture_factory,
    snapshot,
)


class TestInMemoryBackend(unittest.TestCase):

    def test_savepoint_and_rollback(self):
        b = InMemoryBackend()
        b.insert("users", 1, {"name": "alice"})
        b.savepoint("sp1")
        b.insert("users", 2, {"name": "bob"})
        b.rollback_to("sp1")
        self.assertEqual(b.tables["users"], {1: {"name": "alice"}})

    def test_duplicate_savepoint_rejected(self):
        b = InMemoryBackend()
        b.savepoint("sp1")
        with self.assertRaises(DbSnapshotError):
            b.savepoint("sp1")

    def test_unknown_savepoint_rejected(self):
        with self.assertRaises(DbSnapshotError):
            InMemoryBackend().rollback_to("missing")


class TestSnapshotScope(unittest.TestCase):

    def test_create_pushes_handle(self):
        scope = SnapshotScope(backend=InMemoryBackend())
        handle = scope.create()
        self.assertEqual(scope.active(), 1)
        self.assertIsInstance(handle, SnapshotHandle)
        self.assertTrue(handle.name.startswith("wr_snap"))

    def test_rollback_pops_handle(self):
        scope = SnapshotScope(backend=InMemoryBackend())
        h = scope.create()
        scope.rollback(h)
        self.assertEqual(scope.active(), 0)

    def test_rollback_out_of_order_rejected(self):
        scope = SnapshotScope(backend=InMemoryBackend())
        h1 = scope.create()
        scope.create()
        with self.assertRaises(DbSnapshotError):
            scope.rollback(h1)

    def test_rollback_without_active_rejected(self):
        scope = SnapshotScope(backend=InMemoryBackend())
        with self.assertRaises(DbSnapshotError):
            scope.rollback(SnapshotHandle(name="bogus"))

    def test_backend_failure_wrapped(self):
        class BadBackend:
            def savepoint(self, name):
                raise RuntimeError("conn dropped")
            def rollback_to(self, name):
                """Stub rollback — body intentionally empty for this test."""

        scope = SnapshotScope(backend=BadBackend())
        with self.assertRaises(DbSnapshotError):
            scope.create()

    def test_backend_rollback_failure_wrapped(self):
        class BadBackend:
            def savepoint(self, name):
                """Stub savepoint — body intentionally empty for this test."""
            def rollback_to(self, name):
                raise RuntimeError("disk full")

        scope = SnapshotScope(backend=BadBackend())
        h = scope.create()
        with self.assertRaises(DbSnapshotError):
            scope.rollback(h)


class TestSnapshotCtx(unittest.TestCase):

    def test_context_rolls_back_on_success(self):
        b = InMemoryBackend()
        b.insert("u", 1, "a")
        scope = SnapshotScope(backend=b)
        with snapshot(scope):
            b.insert("u", 2, "b")
        self.assertEqual(b.tables["u"], {1: "a"})

    def test_context_rolls_back_on_exception(self):
        b = InMemoryBackend()
        b.insert("u", 1, "a")
        scope = SnapshotScope(backend=b)
        with self.assertRaises(ValueError):
            with snapshot(scope):
                b.insert("u", 2, "b")
                raise ValueError("boom")
        self.assertEqual(b.tables["u"], {1: "a"})

    def test_nested_contexts_unwind_in_order(self):
        b = InMemoryBackend()
        scope = SnapshotScope(backend=b)
        with snapshot(scope):
            b.insert("u", 1, "a")
            with snapshot(scope):
                b.insert("u", 2, "b")
                self.assertEqual(scope.active(), 2)
            self.assertEqual(scope.active(), 1)
            self.assertEqual(b.tables["u"], {1: "a"})
        self.assertEqual(scope.active(), 0)
        self.assertEqual(b.tables.get("u", {}), {})


class TestAssertNoActive(unittest.TestCase):

    def test_empty_passes(self):
        assert_no_active_snapshots(SnapshotScope(backend=InMemoryBackend()))

    def test_leak_detected(self):
        scope = SnapshotScope(backend=InMemoryBackend())
        scope.create()
        with self.assertRaises(DbSnapshotError):
            assert_no_active_snapshots(scope)


class TestPytestFactory(unittest.TestCase):

    def test_factory_iterates(self):
        b = InMemoryBackend()
        b.insert("u", 1, "a")
        fixture = pytest_fixture_factory(b)
        gen = fixture()
        backend = next(gen)
        backend.insert("u", 2, "b")
        # exhaust generator → triggers rollback
        try:
            next(gen)
        except StopIteration:
            pass
        self.assertEqual(b.tables["u"], {1: "a"})


if __name__ == "__main__":
    unittest.main()
