"""
Storybook 視覺快照：把 ``discover_stories`` + ``visual_regression`` 串起來，
每個 story 一張 baseline / current 比對。
Wire :mod:`storybook` discovery into :mod:`visual_regression` so each
story renders into a deterministic baseline filename like
``components-button--primary.png``. Caller supplies the screenshot
function (``driver.get_screenshot_as_png`` / ``page.screenshot``); the
helper handles iteration, naming, and aggregate reporting.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Union

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.utils.storybook.discovery import StorybookStory


class StorybookSnapshotError(WebRunnerException):
    """Raised when iteration / capture / compare fails."""


Screenshot = Callable[[str], bytes]
Comparator = Callable[[bytes, Path], Dict[str, Any]]


def safe_filename(story: StorybookStory) -> str:
    """Convert ``components-button--primary`` -> ``components-button--primary.png``."""
    safe = "".join(
        ch if ch.isalnum() or ch in "-_." else "-"
        for ch in story.id
    ).strip("-")
    if not safe:
        safe = "story"
    return f"{safe}.png"


@dataclass
class SnapshotOutcome:
    story_id: str
    image_path: Path
    matched_baseline: bool
    diff_percent: float = 0.0
    note: Optional[str] = None


@dataclass
class StorybookSnapshotReport:
    outcomes: List[SnapshotOutcome] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(o.matched_baseline for o in self.outcomes)

    @property
    def failures(self) -> List[SnapshotOutcome]:
        return [o for o in self.outcomes if not o.matched_baseline]


def _default_comparator(current_bytes: bytes, baseline_path: Path) -> Dict[str, Any]:
    if not baseline_path.is_file():
        return {"matched": False, "diff_percent": 100.0,
                "note": "baseline missing"}
    if baseline_path.read_bytes() == current_bytes:
        return {"matched": True, "diff_percent": 0.0}
    return {"matched": False, "diff_percent": 100.0,
            "note": "byte-level mismatch"}


def capture_story_snapshots(
    stories: Iterable[StorybookStory],
    base_url: str,
    *,
    output_dir: Union[str, Path],
    take_screenshot: Screenshot,
    navigate: Callable[[str], None],
    baseline_dir: Optional[Union[str, Path]] = None,
    comparator: Optional[Comparator] = None,
) -> StorybookSnapshotReport:
    """
    對每個 story 截圖並（可選）跟 baseline 比對；回傳 :class:`StorybookSnapshotReport`。
    """
    if not isinstance(base_url, str) or not base_url:
        raise StorybookSnapshotError("base_url must be non-empty")
    if not callable(take_screenshot):
        raise StorybookSnapshotError("take_screenshot must be callable")
    if not callable(navigate):
        raise StorybookSnapshotError("navigate must be callable")
    base_url = base_url.rstrip("/")
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    baseline_path_root = Path(baseline_dir) if baseline_dir is not None else None
    compare = comparator or _default_comparator
    report = StorybookSnapshotReport()
    for story in stories:
        outcome = _snapshot_story(
            story, base_url, out_dir, take_screenshot, navigate,
            baseline_path_root, compare,
        )
        report.outcomes.append(outcome)
        web_runner_logger.info(
            f"storybook_snapshots story={story.id!r} matched={outcome.matched_baseline}"
        )
    return report


def _snapshot_story(
    story: StorybookStory,
    base_url: str,
    out_dir: Path,
    take_screenshot: Screenshot,
    navigate: Callable[[str], None],
    baseline_path_root: Optional[Path],
    compare: Comparator,
) -> SnapshotOutcome:
    if not isinstance(story, StorybookStory):
        raise StorybookSnapshotError("stories must be StorybookStory instances")
    url = f"{base_url}/{story.iframe_path}"
    try:
        navigate(url)
        png_bytes = take_screenshot(url)
    except Exception as error:  # pylint: disable=broad-except
        raise StorybookSnapshotError(
            f"snapshot failed for {story.id!r}: {error!r}"
        ) from error
    if not isinstance(png_bytes, (bytes, bytearray)) or not png_bytes:
        raise StorybookSnapshotError(
            f"take_screenshot returned empty payload for {story.id!r}"
        )
    filename = safe_filename(story)
    target = out_dir / filename
    target.write_bytes(png_bytes)
    outcome = SnapshotOutcome(
        story_id=story.id, image_path=target, matched_baseline=True,
    )
    if baseline_path_root is not None:
        comparison = compare(bytes(png_bytes), baseline_path_root / filename)
        outcome.matched_baseline = bool(comparison.get("matched"))
        outcome.diff_percent = float(comparison.get("diff_percent", 0.0))
        outcome.note = comparison.get("note")
    return outcome


def assert_no_visual_regressions(report: StorybookSnapshotReport,
                                 allow_stories: Optional[Iterable[str]] = None) -> None:
    allow = set(allow_stories or [])
    bad = [o for o in report.failures if o.story_id not in allow]
    if bad:
        sample = [
            {"story_id": o.story_id, "diff_percent": o.diff_percent,
             "note": o.note}
            for o in bad[:5]
        ]
        raise StorybookSnapshotError(
            f"{len(bad)} story snapshot regression(s): {sample}"
        )
