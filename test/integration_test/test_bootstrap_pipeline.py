"""
Integration: bootstrapper → action_formatter → action_linter on the seed
sample, plus json_validator schema check.

Confirms the starter template is good enough that a new user can run
``init_workspace`` and immediately get a clean lint pass on the seeded
``actions/sample.json``.
"""
import json
import tempfile
import unittest
from pathlib import Path

from je_web_runner.utils.action_formatter.formatter import format_file
from je_web_runner.utils.bootstrapper.bootstrapper import init_workspace
from je_web_runner.utils.linter.action_linter import lint_action_file


class TestBootstrapPipeline(unittest.TestCase):

    def test_starter_actions_lint_clean(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            init_workspace(tmpdir)
            sample = Path(tmpdir) / "actions" / "sample.json"
            self.assertTrue(sample.is_file(),
                            msg="bootstrapper missing actions/sample.json")
            findings = lint_action_file(str(sample))
            errors = [f for f in findings if f.get("severity") == "error"]
            self.assertEqual(errors, [],
                             msg=f"starter actions had lint errors: {errors}")

    def test_format_idempotent_after_bootstrap(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            init_workspace(tmpdir)
            sample = Path(tmpdir) / "actions" / "sample.json"
            text_a, changed_a = format_file(sample)
            text_b, changed_b = format_file(sample)
            self.assertEqual(text_a, text_b)
            self.assertFalse(changed_b)

    def test_workflow_yaml_present_and_references_module(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            init_workspace(tmpdir)
            workflow = Path(tmpdir) / ".github" / "workflows" / "webrunner.yml"
            content = workflow.read_text(encoding="utf-8")
            self.assertIn("python -m je_web_runner", content)

    def test_schema_file_is_valid_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            init_workspace(tmpdir)
            schema = Path(tmpdir) / ".webrunner" / "action-schema.json"
            data = json.loads(schema.read_text(encoding="utf-8"))
            # The schema we ship is a JSON Schema, so it must declare
            # the standard $schema URL.
            self.assertIn("$schema", data)


if __name__ == "__main__":
    unittest.main()
