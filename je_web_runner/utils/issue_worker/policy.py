"""Conservative patch scope and existing-test assertion preservation."""
from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path, PurePosixPath

from je_web_runner.utils.issue_worker.types import IssueWorkerError

PROTECTED = {"pyproject.toml", "dev.toml", "requirements.txt", "dev_requirements.txt", "uv.lock",
             "CLAUDE.md", "AGENTS.md", "SECURITY.md", "LICENSE"}
ROOT_DOCS = {"README.md", "architecture.md", "progress.md"}


def checked_path(root: Path, name: str, write: bool = False) -> Path:
    """Fence paths to the owned worktree, refusing symlinks and credential files."""
    pure = PurePosixPath(name)
    if not name or "\\" in name or pure.is_absolute() or any(ord(char) < 32 for char in name):
        raise IssueWorkerError("invalid repository path")
    if any(part in {"..", ".git"} or ":" in part for part in pure.parts):
        raise IssueWorkerError("repository path escapes its scope")
    target = root.joinpath(*pure.parts)
    if not target.resolve().is_relative_to(root.resolve()):
        raise IssueWorkerError("repository path escapes the worktree")
    if any(parent.is_symlink() for parent in [target, *target.parents] if parent.is_relative_to(root)):
        raise IssueWorkerError("symlink paths are not available to coding tools")
    basename = pure.name.lower()
    if basename.endswith((".pem", ".key", ".p12", ".pfx")) or (basename.startswith(".env") and
                                                               basename not in {".env.example", ".env.sample"}):
        raise IssueWorkerError("credential files are not available to coding tools")
    if write:
        _write_scope(pure)
    return target


def _write_scope(path: PurePosixPath) -> None:
    allowed = path.parts[0] in {"je_web_runner", "test", "docs", "examples", "README", "scripts"}
    if not allowed and str(path) not in ROOT_DOCS:
        raise IssueWorkerError("patch touches a path outside the coding allowlist")
    forbidden = any(part.startswith(".git") for part in path.parts) or path.name in PROTECTED
    if forbidden or path.name.endswith(".lock") or "requirements" in path.name or "release" in path.name:
        raise IssueWorkerError("patch touches protected configuration, dependencies or release settings")


def assertion_inventory(source: str) -> Counter[str]:
    """Fingerprint existing assert statements and unittest assertion calls."""
    tree = ast.parse(source)
    nodes = [node for node in ast.walk(tree) if isinstance(node, ast.Assert) or (
        isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr.startswith("assert")
    )]
    return Counter(ast.dump(node, include_attributes=False) for node in nodes)


def preserve_tests(before: str, after: str) -> None:
    """Flag changed/deleted assertions, test functions and new skip/xfail escapes."""
    try:
        old_tree, new_tree = ast.parse(before), ast.parse(after)
        if assertion_inventory(before) - assertion_inventory(after):
            raise IssueWorkerError("patch removes or changes an existing test assertion")
        previous = _test_names(old_tree)
        current = _test_names(new_tree)
        if previous - current:
            raise IssueWorkerError("patch removes an existing test function")
        old_skips = _skip_inventory(old_tree)
        if _skip_inventory(new_tree) - old_skips:
            raise IssueWorkerError("patch adds skip or xfail behavior")
    except SyntaxError as error:
        raise IssueWorkerError("patched Python tests must parse successfully") from error


def _skip_inventory(tree: ast.AST) -> Counter[str]:
    names = {"skip", "skipif", "skipIf", "skipUnless", "skipTest", "xfail", "expectedFailure"}
    return Counter(ast.dump(node, include_attributes=False) for node in ast.walk(tree)
                   if (isinstance(node, ast.Attribute) and node.attr in names)
                   or (isinstance(node, ast.Name) and node.id in names))


def _test_names(tree: ast.AST) -> set[str]:
    return {node.name for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")}
