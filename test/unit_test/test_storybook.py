import json
import tempfile
import unittest
from pathlib import Path

from je_web_runner.utils.storybook import (
    StorybookError,
    discover_stories,
    plan_actions_for_stories,
)
from je_web_runner.utils.storybook.discovery import (
    filter_stories_by_kind,
)


def _index(entries):
    return {"v": 5, "entries": entries}


class TestDiscoverStories(unittest.TestCase):

    def test_parses_entries(self):
        document = _index({
            "button--primary": {
                "id": "button--primary",
                "title": "Components/Button",
                "name": "Primary",
                "type": "story",
            },
            "button--docs": {
                "id": "button--docs",
                "title": "Components/Button",
                "name": "Docs",
                "type": "docs",
            },
        })
        stories = discover_stories(document)
        self.assertEqual(len(stories), 1)
        self.assertEqual(stories[0].name, "Primary")

    def test_skip_examples(self):
        document = _index({
            "example--intro": {
                "id": "example--intro",
                "title": "Example/Introduction",
                "name": "Intro",
                "type": "story",
            },
        })
        self.assertEqual(discover_stories(document, skip_examples=True), [])

    def test_keep_examples_when_requested(self):
        document = _index({
            "example--intro": {
                "id": "example--intro",
                "title": "Example/Introduction",
                "name": "Intro",
                "type": "story",
            },
        })
        self.assertEqual(len(discover_stories(document, skip_examples=False)), 1)

    def test_legacy_stories_field(self):
        document = {"v": 4, "stories": {
            "btn": {"id": "btn", "title": "Button", "name": "Default"},
        }}
        stories = discover_stories(document)
        self.assertEqual(stories[0].title, "Button")

    def test_iframe_path(self):
        document = _index({
            "id1": {"id": "id1", "title": "Components/Button", "name": "Primary",
                    "type": "story"},
        })
        story = discover_stories(document)[0]
        self.assertEqual(story.iframe_path,
                         "iframe.html?id=id1&viewMode=story")

    def test_load_from_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "index.json"
            path.write_text(json.dumps(_index({
                "x": {"id": "x", "title": "C/B", "name": "N", "type": "story"},
            })), encoding="utf-8")
            self.assertEqual(len(discover_stories(path)), 1)

    def test_invalid_source_raises(self):
        with self.assertRaises(StorybookError):
            discover_stories(42)  # type: ignore[arg-type]

    def test_missing_entries_raises(self):
        with self.assertRaises(StorybookError):
            discover_stories({"v": 5})


class TestPlanActions(unittest.TestCase):

    def test_visits_a11y_screenshot_per_story(self):
        document = _index({
            "btn": {"id": "btn", "title": "Components/Button", "name": "Primary",
                    "type": "story"},
        })
        stories = discover_stories(document)
        plan = plan_actions_for_stories(
            stories, base_url="http://localhost:6006",
        )
        commands = [a[0] for a in plan]
        self.assertEqual(commands[:3], [
            "WR_to_url", "WR_a11y_run_audit", "WR_get_screenshot_as_png",
        ])

    def test_extras_appended(self):
        document = _index({
            "btn": {"id": "btn", "title": "C/B", "name": "P", "type": "story"},
        })
        stories = discover_stories(document)
        plan = plan_actions_for_stories(
            stories, base_url="http://localhost:6006",
            run_a11y=False, capture_screenshot=False,
            extra_per_story=[["WR_visual_capture_baseline"]],
        )
        self.assertEqual(plan[-1], ["WR_visual_capture_baseline"])

    def test_invalid_base_url(self):
        with self.assertRaises(StorybookError):
            plan_actions_for_stories([], base_url="")


class TestFilterByKind(unittest.TestCase):

    def test_filters_by_title_prefix(self):
        document = _index({
            "btn": {"id": "btn", "title": "Components/Button", "name": "P",
                    "type": "story"},
            "lay": {"id": "lay", "title": "Layouts/Grid", "name": "P",
                    "type": "story"},
        })
        stories = discover_stories(document)
        kept = filter_stories_by_kind(stories, "Components/")
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].title, "Components/Button")


if __name__ == "__main__":
    unittest.main()
