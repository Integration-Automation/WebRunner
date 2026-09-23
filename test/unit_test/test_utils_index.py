"""``docs/reference/utils_index.md`` must match what ``scripts/gen_utils_index.py`` generates.

The index lists every ``je_web_runner/utils`` subpackage by layer. A new subpackage, a moved
facade import or a changed docstring makes it stale; regenerate it with
``python scripts/gen_utils_index.py``.
"""
import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATOR = REPO_ROOT / "scripts" / "gen_utils_index.py"


def _load_generator():
    spec = importlib.util.spec_from_file_location("gen_utils_index", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_committed_index_matches_the_generator():
    generator = _load_generator()
    committed = generator.INDEX_PATH.read_text(encoding="utf-8")
    assert committed == generator.render(), (  # nosec B101
        "docs/reference/utils_index.md is stale; run python scripts/gen_utils_index.py"
    )


def test_every_subpackage_is_listed_once():
    generator = _load_generator()
    text = generator.render()
    for name in generator.subpackages():
        assert text.count(f"| `{name}` |") == 1, name  # nosec B101


def test_core_packages_exist():
    generator = _load_generator()
    assert set(generator.CORE) <= set(generator.subpackages())  # nosec B101
