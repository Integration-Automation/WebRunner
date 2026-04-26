import tempfile
import unittest
from pathlib import Path

from je_web_runner.utils.md_authoring import (
    MdAuthoringError,
    parse_markdown,
    transpile_file,
)
from je_web_runner.utils.md_authoring.markdown_to_actions import (
    supported_bullet_patterns,
)


class TestParseMarkdown(unittest.TestCase):

    def test_open_url(self):
        actions = parse_markdown("- open https://example.com")
        self.assertEqual(actions, [["WR_to_url", {"url": "https://example.com"}]])

    def test_click_id_selector(self):
        actions = parse_markdown("- click #submit")
        self.assertEqual(actions[0],
                         ["WR_save_test_object",
                          {"test_object_name": "submit", "object_type": "ID"}])
        self.assertEqual(actions[-1], ["WR_element_click"])

    def test_type_into(self):
        actions = parse_markdown('- type "alice" into #user')
        commands = [a[0] for a in actions]
        self.assertEqual(commands, [
            "WR_save_test_object",
            "WR_find_recorded_element",
            "WR_element_input",
        ])
        self.assertIn("alice", repr(actions))

    def test_wait_seconds(self):
        actions = parse_markdown("- wait 3s")
        self.assertEqual(actions, [
            ["WR_implicitly_wait", {"time_to_wait": 3}],
        ])

    def test_wait_fraction_seconds(self):
        actions = parse_markdown("- wait 1.5s")
        self.assertEqual(actions, [
            ["WR_implicitly_wait", {"time_to_wait": 1.5}],
        ])

    def test_assert_title(self):
        actions = parse_markdown('- assert title "Welcome"')
        self.assertEqual(actions, [["WR_assert_title", {"value": "Welcome"}]])

    def test_press_key(self):
        actions = parse_markdown("- press Enter")
        self.assertEqual(actions, [["WR_press_keys", {"keys": "Enter"}]])

    def test_screenshot(self):
        actions = parse_markdown("- screenshot")
        self.assertEqual(actions, [["WR_get_screenshot_as_png"]])

    def test_render_template(self):
        actions = parse_markdown("- run template login_basic")
        self.assertEqual(
            actions,
            [["WR_render_template", {"template": "login_basic"}]],
        )

    def test_quit(self):
        actions = parse_markdown("- quit")
        self.assertEqual(actions, [["WR_quit_all"]])

    def test_unrecognised_preserved_as_note(self):
        actions = parse_markdown("- swipe gestures here")
        self.assertEqual(actions, [["WR__note", {"text": "swipe gestures here"}]])

    def test_empty_markdown_raises(self):
        with self.assertRaises(MdAuthoringError):
            parse_markdown("")

    def test_non_string_raises(self):
        with self.assertRaises(MdAuthoringError):
            parse_markdown(42)  # type: ignore[arg-type]

    def test_supported_patterns_includes_open(self):
        self.assertIn("open <url>", supported_bullet_patterns())


class TestTranspileFile(unittest.TestCase):

    def test_writes_output(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            md = Path(tmpdir) / "tour.md"
            md.write_text(
                "- open https://example.com\n- click #submit\n- quit\n",
                encoding="utf-8",
            )
            out = Path(tmpdir) / "tour.json"
            actions = transpile_file(md, out)
            self.assertGreater(len(actions), 0)
            self.assertTrue(out.is_file())
            self.assertIn('"WR_to_url"', out.read_text(encoding="utf-8"))

    def test_missing_md_raises(self):
        with self.assertRaises(MdAuthoringError):
            transpile_file("does/not/exist.md")


if __name__ == "__main__":
    unittest.main()
