"""`dev.toml` says it is kept in step with `pyproject.toml`; this checks that it is.

The dev channel (`je_web_runner_dev`) is built by swapping `dev.toml` in for `pyproject.toml`, so a
dependency added on one side and not the other ships a package that imports something it never
declared. `Pillow` was missing from `dev.toml` for exactly that reason (`progress.md` #2).
"""
from pathlib import Path

import pytest

tomllib = pytest.importorskip("tomllib")  # reason: stdlib from 3.11; CI also runs 3.10

REPO_ROOT = Path(__file__).resolve().parents[2]


def _project(name: str) -> dict:
    with (REPO_ROOT / name).open("rb") as handle:
        return tomllib.load(handle)["project"]


STABLE = _project("pyproject.toml")
DEV = _project("dev.toml")


def test_package_names_differ():
    assert STABLE["name"] == "je_web_runner"  # nosec B101
    assert DEV["name"] == "je_web_runner_dev"  # nosec B101


def test_runtime_dependencies_match():
    assert sorted(DEV["dependencies"]) == sorted(STABLE["dependencies"])  # nosec B101


def test_python_floor_matches():
    assert DEV["requires-python"] == STABLE["requires-python"]  # nosec B101


def test_optional_dependency_groups_match():
    assert DEV.get("optional-dependencies", {}) == STABLE.get("optional-dependencies", {})  # nosec B101


def test_entry_points_match():
    assert DEV.get("scripts", {}) == STABLE.get("scripts", {})  # nosec B101
