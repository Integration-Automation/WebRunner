import tempfile
import unittest
from pathlib import Path

from je_web_runner.utils.storybook.discovery import StorybookStory
from je_web_runner.utils.storybook.visual_snapshots import (
    StorybookSnapshotError,
    assert_no_visual_regressions,
    capture_story_snapshots,
    safe_filename,
)


def _story(story_id="components-button--primary", title="Components/Button",
           name="Primary"):
    return StorybookStory(id=story_id, title=title, name=name, kind="story")


class TestSafeFilename(unittest.TestCase):

    def test_simple(self):
        self.assertEqual(
            safe_filename(_story("components-button--primary")),
            "components-button--primary.png",
        )

    def test_unsafe_characters_replaced(self):
        self.assertEqual(
            safe_filename(_story("space here / weird")),
            "space-here---weird.png",
        )

    def test_empty_id_falls_back(self):
        self.assertEqual(
            safe_filename(_story("")),
            "story.png",
        )


class TestCaptureStorySnapshots(unittest.TestCase):

    def test_writes_pngs_no_baseline(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "out"
            visited = []
            report = capture_story_snapshots(
                [_story("a"), _story("b")],
                base_url="http://localhost:6006",
                output_dir=out,
                take_screenshot=lambda _url: b"\x89PNG\r\n",
                navigate=visited.append,
            )
            self.assertEqual(len(report.outcomes), 2)
            self.assertTrue((out / "a.png").is_file())
            self.assertTrue(report.passed)
            self.assertEqual(len(visited), 2)

    def test_baseline_match_passes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "out"
            baseline = Path(tmpdir) / "baseline"
            baseline.mkdir()
            (baseline / "a.png").write_bytes(b"matching")
            report = capture_story_snapshots(
                [_story("a")],
                base_url="http://localhost:6006",
                output_dir=out,
                baseline_dir=baseline,
                take_screenshot=lambda _url: b"matching",
                navigate=lambda _url: None,
            )
            self.assertTrue(report.passed)

    def test_baseline_missing_flags_failure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "out"
            baseline = Path(tmpdir) / "baseline"
            baseline.mkdir()
            report = capture_story_snapshots(
                [_story("a")],
                base_url="http://localhost:6006",
                output_dir=out,
                baseline_dir=baseline,
                take_screenshot=lambda _url: b"new",
                navigate=lambda _url: None,
            )
            self.assertFalse(report.passed)
            self.assertEqual(report.failures[0].note, "baseline missing")

    def test_byte_level_mismatch(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "out"
            baseline = Path(tmpdir) / "baseline"
            baseline.mkdir()
            (baseline / "a.png").write_bytes(b"old")
            report = capture_story_snapshots(
                [_story("a")],
                base_url="http://localhost:6006",
                output_dir=out,
                baseline_dir=baseline,
                take_screenshot=lambda _url: b"new",
                navigate=lambda _url: None,
            )
            self.assertFalse(report.passed)

    def test_screenshot_must_return_bytes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "out"
            with self.assertRaises(StorybookSnapshotError):
                capture_story_snapshots(
                    [_story("a")],
                    base_url="http://localhost:6006",
                    output_dir=out,
                    take_screenshot=lambda _url: b"",
                    navigate=lambda _url: None,
                )

    def test_screenshot_callable_required(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(StorybookSnapshotError):
                capture_story_snapshots(
                    [],
                    base_url="http://x",
                    output_dir=tmpdir,
                    take_screenshot="not callable",  # type: ignore[arg-type]
                    navigate=lambda _url: None,
                )

    def test_invalid_base_url(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(StorybookSnapshotError):
                capture_story_snapshots(
                    [],
                    base_url="",
                    output_dir=tmpdir,
                    take_screenshot=lambda _url: b"x",
                    navigate=lambda _url: None,
                )


class TestAssertNoVisualRegressions(unittest.TestCase):

    def test_passes_clean(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "out"
            report = capture_story_snapshots(
                [_story("a")],
                base_url="http://x",
                output_dir=out,
                take_screenshot=lambda _url: b"x",
                navigate=lambda _url: None,
            )
            assert_no_visual_regressions(report)

    def test_raises_on_failure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "out"
            baseline = Path(tmpdir) / "baseline"
            baseline.mkdir()
            (baseline / "a.png").write_bytes(b"old")
            report = capture_story_snapshots(
                [_story("a")],
                base_url="http://x",
                output_dir=out,
                baseline_dir=baseline,
                take_screenshot=lambda _url: b"new",
                navigate=lambda _url: None,
            )
            with self.assertRaises(StorybookSnapshotError):
                assert_no_visual_regressions(report)

    def test_allow_stories_skips(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "out"
            baseline = Path(tmpdir) / "baseline"
            baseline.mkdir()
            report = capture_story_snapshots(
                [_story("a")],
                base_url="http://x",
                output_dir=out,
                baseline_dir=baseline,
                take_screenshot=lambda _url: b"new",
                navigate=lambda _url: None,
            )
            assert_no_visual_regressions(report, allow_stories=["a"])


if __name__ == "__main__":
    unittest.main()
