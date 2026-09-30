"""The Selenium / Playwright comparison names only commands the executor registers."""
import re
from pathlib import Path

import pytest

from je_web_runner.utils.executor.action_executor import executor

_ROOT = Path(__file__).resolve().parents[2]
_PAGES = [
    _ROOT / "docs" / "source" / "Eng" / "doc" / "backends" / "backends_doc.rst",
    _ROOT / "docs" / "source" / "Zh" / "doc" / "backends" / "backends_doc.rst",
]
# A name followed by "*" or ending in "_" is a family (``WR_sw_*``) or a suffix
# fragment (``WR_element_select_by_value`` / ``_by_index``), not one command.
_COMMAND = re.compile(r"\bWR_[A-Za-z0-9_]*[A-Za-z0-9](?![A-Za-z0-9_*])")


@pytest.mark.parametrize("page", _PAGES, ids=lambda page: page.parts[-4])
def test_every_command_named_on_the_backends_page_is_registered(page):
    names = set(_COMMAND.findall(page.read_text(encoding="utf-8")))
    assert names, f"no WR_ command found in {page}"  # nosec B101
    missing = sorted(name for name in names if name not in executor.event_dict)
    assert missing == []  # nosec B101


def test_both_languages_name_the_same_commands():
    english, chinese = (set(_COMMAND.findall(page.read_text(encoding="utf-8"))) for page in _PAGES)
    assert english == chinese  # nosec B101
