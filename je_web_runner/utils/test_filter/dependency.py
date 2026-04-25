"""
Action 檔的依賴關係：``meta.depends_on`` 宣告，依拓樸排序執行，前置失敗則跳過。
Action-file dependencies via ``meta.depends_on``: files run in topological
order, downstream files are skipped (recorded as failed) when their
upstream dependencies fail.
"""
from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.utils.test_filter.tag_filter import read_metadata


class DependencyError(WebRunnerException):
    """Raised when a dependency declaration cannot be resolved."""


def _basename_key(path: str) -> str:
    return Path(path).stem


def read_depends_on(path: str) -> List[str]:
    """讀取單一檔案的 ``meta.depends_on`` 清單（以 basename 表示）。"""
    meta = read_metadata(path)
    deps = meta.get("depends_on") or []
    return [str(dep) for dep in deps if isinstance(dep, str)]


def build_dependency_graph(paths: Sequence[str]) -> Dict[str, List[str]]:
    """
    依基本檔名建立 ``{path: [dep_path, ...]}`` 圖
    Build a ``{path: [dep_path, …]}`` graph by matching ``depends_on`` entries
    against the basenames of the input paths.

    無法對應到 ``paths`` 中任何檔案的依賴會被忽略並寫入 log（避免阻擋執行）。
    Dependencies that do not match any input path are dropped with a warning.
    """
    by_stem: Dict[str, str] = {_basename_key(path): path for path in paths}
    graph: Dict[str, List[str]] = {path: [] for path in paths}
    for path in paths:
        for dep_name in read_depends_on(path):
            dep_path = by_stem.get(dep_name)
            if dep_path is None:
                web_runner_logger.warning(
                    f"dependency {dep_name!r} declared by {path!r} not found in selection"
                )
                continue
            if dep_path == path:
                continue
            graph[path].append(dep_path)
    return graph


def topological_order(graph: Dict[str, List[str]]) -> List[str]:
    """
    Kahn 演算法拓樸排序；偵測環時拋例外
    Kahn's algorithm; raises DependencyError on cycle.
    """
    in_degree: Dict[str, int] = defaultdict(int)
    successors: Dict[str, List[str]] = defaultdict(list)
    nodes = list(graph.keys())
    for node in nodes:
        in_degree[node] = in_degree[node] + 0
    for node, deps in graph.items():
        for dep in deps:
            successors[dep].append(node)
            in_degree[node] += 1

    ready = deque(node for node in nodes if in_degree[node] == 0)
    ordered: List[str] = []
    while ready:
        current = ready.popleft()
        ordered.append(current)
        for follower in successors[current]:
            in_degree[follower] -= 1
            if in_degree[follower] == 0:
                ready.append(follower)
    if len(ordered) != len(nodes):
        raise DependencyError("dependency cycle detected; cannot order tests")
    return ordered


def _node_should_skip(
    node: str,
    deps: List[str],
    failed_set: set,
    must_skip: set,
) -> bool:
    if node in failed_set or node in must_skip:
        return False
    return any(dep in failed_set or dep in must_skip for dep in deps)


def skip_dependents_of_failed(
    graph: Dict[str, List[str]],
    failed: Iterable[str],
) -> List[str]:
    """
    回傳因為上游失敗而應該跳過的檔案
    Return files whose ancestry contains any path in ``failed``.
    """
    failed_set = set(failed)
    must_skip: set = set()
    while True:
        added = False
        for node, deps in graph.items():
            if _node_should_skip(node, deps, failed_set, must_skip):
                must_skip.add(node)
                added = True
        if not added:
            break
    return list(must_skip)


def order_paths_by_dependency(paths: Sequence[str]) -> List[str]:
    """
    便捷函式：建圖並回傳拓樸序
    Convenience: build graph and return paths in topological order.
    """
    return topological_order(build_dependency_graph(paths))
