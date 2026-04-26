"""
Test name regex 篩選：用 ``--include`` / ``--exclude`` regex 過濾 action JSON 檔。
Regex-based filename selector. Pairs with the existing tag-based filter
to give the runner two orthogonal ways to narrow a run: ``include`` keeps
only paths matching at least one positive pattern, ``exclude`` drops any
path matching a negative pattern. Both lists support full ``re`` syntax.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Union

from je_web_runner.utils.exception.exceptions import WebRunnerException


class NameFilterError(WebRunnerException):
    """Raised when a regex pattern can't be compiled."""


@dataclass
class NameFilter:
    """Compiled include / exclude regex sets."""

    include: List[re.Pattern] = field(default_factory=list)
    exclude: List[re.Pattern] = field(default_factory=list)

    def matches(self, path: Union[str, Path]) -> bool:
        text = str(path).replace("\\", "/")
        for pattern in self.exclude:
            if pattern.search(text):
                return False
        if not self.include:
            return True
        return any(pattern.search(text) for pattern in self.include)


def _compile_each(patterns: Optional[Sequence[str]]) -> List[re.Pattern]:
    compiled: List[re.Pattern] = []
    for index, pattern in enumerate(patterns or []):
        if not isinstance(pattern, str) or not pattern:
            raise NameFilterError(f"pattern[{index}] must be non-empty string")
        try:
            compiled.append(re.compile(pattern))
        except re.error as error:
            raise NameFilterError(
                f"pattern[{index}] {pattern!r} did not compile: {error}"
            ) from error
    return compiled


def build_filter(
    include: Optional[Sequence[str]] = None,
    exclude: Optional[Sequence[str]] = None,
) -> NameFilter:
    """Compile ``include`` / ``exclude`` regex lists."""
    return NameFilter(
        include=_compile_each(include),
        exclude=_compile_each(exclude),
    )


def filter_paths(
    paths: Iterable[Union[str, Path]],
    include: Optional[Sequence[str]] = None,
    exclude: Optional[Sequence[str]] = None,
) -> List[str]:
    """Return only those ``paths`` whose name matches the include / exclude rules."""
    name_filter = build_filter(include=include, exclude=exclude)
    return [str(path) for path in paths if name_filter.matches(path)]
