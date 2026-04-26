"""
Storybook 整合：解析 stories.json / index.json，產生每個 story 的測試 action 計畫。
Storybook integration. Reads the ``index.json`` (or legacy
``stories.json``) emitted by Storybook 7+ and projects it into a list of
:class:`StorybookStory` records, then builds a per-story action plan
that visits each in iframe mode and runs accessibility / visual checks.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Union

from je_web_runner.utils.exception.exceptions import WebRunnerException


class StorybookError(WebRunnerException):
    """Raised when Storybook metadata can't be parsed."""


@dataclass(frozen=True)
class StorybookStory:
    id: str
    title: str
    name: str
    kind: str = "story"
    parameters: Optional[Dict[str, Any]] = None

    @property
    def iframe_path(self) -> str:
        """Storybook serves stories on ``/iframe.html?id=<id>&viewMode=story``."""
        return f"iframe.html?id={self.id}&viewMode=story"


def discover_stories(
    source: Union[str, Path, Dict[str, Any]],
    skip_examples: bool = True,
) -> List[StorybookStory]:
    """
    從 ``index.json`` / ``stories.json`` 抽出每個 story 的最小描述
    Read a Storybook index file (or in-memory dict) and return the list of
    stories. ``skip_examples`` filters the ``Example/Introduction`` story
    that the default-init template ships with.
    """
    items = _entries_map(_load(source))
    stories: List[StorybookStory] = []
    for story_id, payload in items.items():
        story = _story_from_entry(story_id, payload, skip_examples)
        if story is not None:
            stories.append(story)
    return stories


def _entries_map(document: Dict[str, Any]) -> Dict[str, Any]:
    items = document.get("entries") or document.get("stories")
    if items is None:
        raise StorybookError("index missing 'entries' / 'stories' map")
    if not isinstance(items, dict):
        raise StorybookError("entries must be a mapping")
    return items


def _story_from_entry(story_id: Any, payload: Any,
                      skip_examples: bool) -> Optional[StorybookStory]:
    if not isinstance(payload, dict):
        raise StorybookError(f"entry {story_id!r} must be an object")
    kind = str(payload.get("type") or payload.get("kind") or "story")
    if kind != "story":
        return None
    title = str(payload.get("title") or "")
    if skip_examples and title.startswith("Example/"):
        return None
    name = str(payload.get("name") or "")
    parameters = payload.get("parameters")
    return StorybookStory(
        id=str(payload.get("id") or story_id),
        title=title,
        name=name,
        kind="story",
        parameters=parameters if isinstance(parameters, dict) else None,
    )


def _load(source: Union[str, Path, Dict[str, Any]]) -> Dict[str, Any]:
    if isinstance(source, dict):
        return source
    if isinstance(source, (str, Path)):
        path = Path(source)
        if not path.is_file():
            raise StorybookError(f"index file not found: {source!r}")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except ValueError as error:
            raise StorybookError(f"index not valid JSON: {error}") from error
    raise StorybookError(f"unsupported source type: {type(source).__name__}")


def plan_actions_for_stories(
    stories: Iterable[StorybookStory],
    base_url: str,
    *,
    run_a11y: bool = True,
    capture_screenshot: bool = True,
    extra_per_story: Optional[Sequence[List[Any]]] = None,
) -> List[List[Any]]:
    """
    對每個 story 產生 ``[navigate, optional a11y, optional screenshot, extras]``。
    Build a flat action list that visits each story under ``base_url`` and
    optionally runs the axe-core audit + screenshot. ``extra_per_story``
    is appended verbatim after the per-story block.
    """
    if not isinstance(base_url, str) or not base_url:
        raise StorybookError("base_url must be non-empty")
    base_url = base_url.rstrip("/")
    actions: List[List[Any]] = []
    extras = list(extra_per_story or [])
    for story in stories:
        url = f"{base_url}/{story.iframe_path}"
        actions.append(["WR_to_url", {"url": url}])
        if run_a11y:
            actions.append(["WR_a11y_run_audit"])
        if capture_screenshot:
            actions.append(["WR_get_screenshot_as_png"])
        actions.extend([list(extra) for extra in extras])
    return actions


def filter_stories_by_kind(
    stories: Iterable[StorybookStory],
    kind_prefix: str,
) -> List[StorybookStory]:
    """Return stories whose ``title`` starts with ``kind_prefix``."""
    return [s for s in stories if s.title.startswith(kind_prefix)]
