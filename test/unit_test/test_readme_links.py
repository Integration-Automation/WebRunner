"""Relative links in every README resolve to a file in the repository.

The translated READMEs live one directory below the root, but some were written
with root-relative targets such as ``docs/mcp.md``, so on GitHub those links led
nowhere. From a translation, ``[x](../LICENSE)`` resolves and ``[x](LICENSE)``
does not.
"""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
_LINK = re.compile(r"\]\(([^)\s]+)[^)]*\)|(?:src|href)=\"([^\"]+)\"")
_FENCE = re.compile(r"```.*?```", re.DOTALL)
_SCHEME = re.compile(r"[a-z][a-z0-9+.-]*:", re.IGNORECASE)
_READMES = sorted([*REPO_ROOT.glob("README*.md"), *REPO_ROOT.glob("README/*.md")])


def _broken_links(readme: Path) -> list[str]:
    """Return the relative link targets in ``readme`` that point at no file.

    URLs, in-page anchors and anything inside a fenced code block are skipped.
    """
    text = _FENCE.sub("", readme.read_text(encoding="utf-8"))
    broken = []
    for match in _LINK.finditer(text):
        target = match.group(1) or match.group(2)
        if _SCHEME.match(target) or target.startswith(("#", "/")):
            continue
        path = unquote(target.split("#")[0].split("?")[0])
        if path and not (readme.parent / path).exists():
            broken.append(target)
    return broken


def test_readmes_found():
    assert len(_READMES) > 1  # nosec B101 — assert is the test assertion


@pytest.mark.parametrize("readme", _READMES, ids=lambda p: p.relative_to(REPO_ROOT).as_posix())
def test_relative_links_resolve(readme):
    assert _broken_links(readme) == []  # nosec B101 — assert is the test assertion
