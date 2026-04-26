"""
Coverage map：把 action JSON 走過的 URL routes 反向索引，方便回答
「哪些測試會碰到 ``/checkout``？」、「哪個 route 沒有任何測試覆蓋？」。
Reverse index of action JSON files by the URL routes they navigate to.
``WR_to_url`` / ``WR_pw_to_url`` calls are walked, the path component is
extracted (with optional path-parameter normalisation), and the result
is keyed by route → set of files.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Union
from urllib.parse import urlparse

from je_web_runner.utils.exception.exceptions import WebRunnerException


class CoverageMapError(WebRunnerException):
    """Raised on invalid input or unreadable action JSON."""


_NAVIGATION_COMMANDS = {
    "WR_to_url",
    "WR_pw_to_url",
    "WR_get_url",
}


_NUMERIC_SEGMENT = re.compile(r"^\d+$")
_UUID_SEGMENT = re.compile(r"^[0-9a-fA-F-]{8,}$")


def normalise_path(path: str, normalise_params: bool = True) -> str:
    """Strip query / fragment and replace numeric or UUID segments with ``:id``."""
    cleaned = path.split("?", 1)[0].split("#", 1)[0] or "/"
    if not normalise_params:
        return cleaned
    parts = cleaned.split("/")
    canonical = []
    for segment in parts:
        if not segment:
            canonical.append(segment)
            continue
        if _NUMERIC_SEGMENT.match(segment) or _UUID_SEGMENT.match(segment):
            canonical.append(":id")
        else:
            canonical.append(segment)
    return "/".join(canonical)


def _extract_url(action: List[Any]) -> Optional[str]:
    if not isinstance(action, list) or len(action) < 2:
        return None
    command = action[0]
    if not isinstance(command, str) or command not in _NAVIGATION_COMMANDS:
        return None
    body = action[1]
    if isinstance(body, dict):
        return body.get("url")
    if len(action) >= 3 and isinstance(action[2], dict):
        return action[2].get("url")
    if isinstance(body, list) and body:
        return body[0] if isinstance(body[0], str) else None
    return None


def _path_for(url: str) -> str:
    parsed = urlparse(url)
    if parsed.path:
        return parsed.path
    if parsed.netloc:
        return "/"
    return url  # likely a relative path supplied by the test author


@dataclass
class CoverageMap:
    routes_by_file: Dict[str, Set[str]] = field(default_factory=dict)
    files_by_route: Dict[str, Set[str]] = field(default_factory=dict)

    def files_for(self, route: str) -> List[str]:
        return sorted(self.files_by_route.get(route, set()))

    def routes_for(self, file_path: str) -> List[str]:
        return sorted(self.routes_by_file.get(file_path, set()))

    def all_routes(self) -> List[str]:
        return sorted(self.files_by_route.keys())

    def uncovered(self, declared_routes: Iterable[str]) -> List[str]:
        return sorted(set(declared_routes) - set(self.files_by_route.keys()))


def build_coverage_map(
    directory: Union[str, Path],
    glob: str = "**/*.json",
    normalise_params: bool = True,
) -> CoverageMap:
    """Walk ``directory`` for action JSON files and build the coverage map."""
    base = Path(directory)
    if not base.is_dir():
        raise CoverageMapError(f"directory missing: {directory!r}")
    routes_by_file: Dict[str, Set[str]] = defaultdict(set)
    files_by_route: Dict[str, Set[str]] = defaultdict(set)
    for path in sorted(base.glob(glob)):
        if not path.is_file():
            continue
        actions = _load_action_list(path)
        if actions is None:
            continue
        for route in _routes_in(actions, normalise_params):
            routes_by_file[str(path)].add(route)
            files_by_route[route].add(str(path))
    return CoverageMap(
        routes_by_file=dict(routes_by_file),
        files_by_route=dict(files_by_route),
    )


def _load_action_list(path: Path) -> Optional[List[Any]]:
    try:
        actions = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return None
    return actions if isinstance(actions, list) else None


def _routes_in(actions: List[Any], normalise_params: bool):
    for action in actions:
        if not isinstance(action, list):
            continue
        url = _extract_url(action)
        if not isinstance(url, str) or not url:
            continue
        yield normalise_path(_path_for(url), normalise_params=normalise_params)


def coverage_for_routes(
    coverage: CoverageMap,
    declared_routes: Sequence[str],
) -> Dict[str, List[str]]:
    """Return ``{route: [files]}`` for each declared route (empty list if missing)."""
    return {route: coverage.files_for(route) for route in declared_routes}


def render_markdown(coverage: CoverageMap,
                    declared_routes: Optional[Sequence[str]] = None) -> str:
    """Render a Markdown coverage report (table of route → file count)."""
    routes = list(declared_routes) if declared_routes else coverage.all_routes()
    lines = [
        "| Route | Tests | Files |",
        "|---|---|---|",
    ]
    for route in routes:
        files = coverage.files_for(route)
        files_text = "<br>".join(files) if files else "_uncovered_"
        lines.append(f"| `{route}` | {len(files)} | {files_text} |")
    return "\n".join(lines) + "\n"
