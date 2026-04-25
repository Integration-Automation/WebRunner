import json
import os
import tempfile
import unittest
from pathlib import Path

from je_web_runner.utils.test_filter.dependency import (
    DependencyError,
    build_dependency_graph,
    order_paths_by_dependency,
    read_depends_on,
    skip_dependents_of_failed,
    topological_order,
)


def _write(directory, name, payload):
    path = os.path.join(directory, name)
    Path(path).write_text(json.dumps(payload), encoding="utf-8")
    return path


def _action(deps=None):
    return {
        "webdriver_wrapper": [["WR_quit"]],
        "meta": {"depends_on": deps or []},
    }


class TestReadDependsOn(unittest.TestCase):

    def test_no_meta_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _write(tmpdir, "a.json", [["WR_quit"]])
            self.assertEqual(read_depends_on(path), [])

    def test_returns_list(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _write(tmpdir, "checkout.json", _action(deps=["login"]))
            self.assertEqual(read_depends_on(path), ["login"])


class TestBuildGraph(unittest.TestCase):

    def test_dependency_resolved_by_basename(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            login = _write(tmpdir, "login.json", _action())
            checkout = _write(tmpdir, "checkout.json", _action(deps=["login"]))
            graph = build_dependency_graph([login, checkout])
            self.assertEqual(graph[checkout], [login])
            self.assertEqual(graph[login], [])

    def test_unknown_dependency_dropped(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            checkout = _write(tmpdir, "checkout.json", _action(deps=["missing"]))
            self.assertEqual(build_dependency_graph([checkout])[checkout], [])

    def test_self_dependency_skipped(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            login = _write(tmpdir, "login.json", _action(deps=["login"]))
            self.assertEqual(build_dependency_graph([login])[login], [])


class TestTopologicalOrder(unittest.TestCase):

    def test_orders_dependencies_first(self):
        graph = {"a": [], "b": ["a"], "c": ["b"]}
        ordered = topological_order(graph)
        self.assertLess(ordered.index("a"), ordered.index("b"))
        self.assertLess(ordered.index("b"), ordered.index("c"))

    def test_cycle_raises(self):
        graph = {"a": ["b"], "b": ["a"]}
        with self.assertRaises(DependencyError):
            topological_order(graph)

    def test_independent_nodes_all_present(self):
        graph = {"a": [], "b": [], "c": []}
        self.assertEqual(set(topological_order(graph)), {"a", "b", "c"})


class TestSkipDependents(unittest.TestCase):

    def test_direct_dependent_skipped(self):
        graph = {"a": [], "b": ["a"]}
        self.assertEqual(skip_dependents_of_failed(graph, ["a"]), ["b"])

    def test_transitive_skipped(self):
        graph = {"a": [], "b": ["a"], "c": ["b"]}
        skipped = skip_dependents_of_failed(graph, ["a"])
        self.assertEqual(set(skipped), {"b", "c"})

    def test_no_failures_no_skips(self):
        graph = {"a": [], "b": ["a"]}
        self.assertEqual(skip_dependents_of_failed(graph, []), [])


class TestOrderPaths(unittest.TestCase):

    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            login = _write(tmpdir, "login.json", _action())
            checkout = _write(tmpdir, "checkout.json", _action(deps=["login"]))
            ordered = order_paths_by_dependency([checkout, login])
            self.assertEqual(ordered, [login, checkout])


if __name__ == "__main__":
    unittest.main()
