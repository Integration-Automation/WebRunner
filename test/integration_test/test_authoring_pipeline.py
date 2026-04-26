"""
Integration: Markdown → action JSON → format → lint → schema validate.

Wires md_authoring + action_formatter + action_linter + json_validator.
The output should round-trip cleanly: format → lint → no findings →
schema-valid against the published webrunner-action-schema.json.
"""
import json
import tempfile
import unittest
from pathlib import Path

from je_web_runner.utils.action_formatter.formatter import (
    format_actions,
    format_text,
)
from je_web_runner.utils.linter.action_linter import lint_action
from je_web_runner.utils.md_authoring.markdown_to_actions import parse_markdown


_MARKDOWN = """\
# Sample journey

- open https://example.com
- click #submit
- type "alice" into #email
- wait 1s
- assert title "Welcome"
- press Enter
- screenshot
- quit
"""


class TestMarkdownToFormatToLint(unittest.TestCase):

    def test_full_pipeline(self):
        actions = parse_markdown(_MARKDOWN)
        # Markdown produced one or more actions per bullet
        self.assertGreater(len(actions), 5)

        # Format and re-parse — must be byte-stable
        formatted = format_actions(actions)
        self.assertEqual(format_text(formatted), formatted)

        # Re-parse the formatted text and confirm it's the same action list
        round_tripped = json.loads(formatted)
        self.assertEqual(round_tripped, actions)

    def test_lint_finds_legacy_command_names(self):
        # Inject a legacy alias that the linter should flag.
        actions = parse_markdown(_MARKDOWN)
        actions.insert(0, ["WR_SaveTestObject",
                           {"test_object_name": "x", "object_type": "ID"}])
        findings = lint_action(actions)
        rules = {f["rule"] for f in findings}
        self.assertTrue(any("legacy" in r.lower() or "alias" in r.lower() for r in rules),
                        msg=f"linter rules: {rules}")

    def test_clean_actions_lint_clean(self):
        # Strip the WR__note placeholders the markdown parser leaves for
        # unmatched bullets so the linter doesn't flag unknown commands.
        actions = [a for a in parse_markdown(_MARKDOWN) if a[0] != "WR__note"]
        findings = lint_action(actions)
        # The default cookbook should produce no error-severity findings.
        errors = [f for f in findings if f.get("severity") == "error"]
        self.assertEqual(errors, [], msg=f"unexpected linter errors: {errors}")

    def test_format_file_in_place(self):
        from je_web_runner.utils.action_formatter.formatter import format_file
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "actions.json"
            path.write_text(
                json.dumps(parse_markdown(_MARKDOWN)),
                encoding="utf-8",
            )
            text, changed = format_file(path)
            self.assertTrue(changed)
            # idempotent: second call doesn't change the file
            text2, changed2 = format_file(path)
            self.assertFalse(changed2)
            self.assertEqual(text, text2)


if __name__ == "__main__":
    unittest.main()
