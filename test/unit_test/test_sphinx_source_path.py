"""Documentation imports the checkout containing its configuration, independently of cwd."""
from pathlib import Path
import runpy
import sys


def test_sphinx_source_uses_the_current_checkout(tmp_path, monkeypatch):
    repository = Path(__file__).resolve().parents[2]
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "path", list(sys.path))
    runpy.run_path(str(repository / "docs" / "source" / "conf.py"))
    assert Path(sys.path[0]).resolve() == repository
