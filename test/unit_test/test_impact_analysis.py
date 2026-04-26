import json
import tempfile
import unittest
from pathlib import Path

from je_web_runner.utils.impact_analysis import (
    ImpactAnalysisError,
    affected_action_files,
    build_index,
)


def _write_actions(path, actions):
    Path(path).write_text(json.dumps(actions), encoding="utf-8")


class TestBuildIndex(unittest.TestCase):

    def test_indexes_locators_urls_templates_commands(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            a = Path(tmpdir) / "a.json"
            b = Path(tmpdir) / "b.json"
            _write_actions(a, [
                ["WR_to_url", {"url": "https://example.com/login"}],
                ["WR_save_test_object", {"test_object_name": "submit_btn",
                                         "object_type": "ID"}],
                ["WR_render_template", {"template": "login_basic"}],
            ])
            _write_actions(b, [
                ["WR_to_url", {"url": "https://example.com/checkout"}],
                ["WR_find_recorded_element", {"element_name": "submit_btn"}],
            ])
            index = build_index(tmpdir)
            self.assertIn(str(a), index.files_for_locator("submit_btn"))
            self.assertIn(str(b), index.files_for_locator("submit_btn"))
            self.assertEqual(
                index.files_for_url("login"),
                [str(a)],
            )
            self.assertEqual(
                index.files_for_template("login_basic"),
                [str(a)],
            )
            self.assertIn(str(a), index.files_for_command("WR_to_url"))
            self.assertIn(str(b), index.files_for_command("WR_to_url"))

    def test_missing_directory_raises(self):
        with self.assertRaises(ImpactAnalysisError):
            build_index("does/not/exist")

    def test_invalid_json_skipped(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "broken.json").write_text("not json", encoding="utf-8")
            ok = Path(tmpdir) / "ok.json"
            _write_actions(ok, [["WR_quit_all"]])
            index = build_index(tmpdir)
            self.assertEqual(index.files_for_command("WR_quit_all"), [str(ok)])


class TestAffectedActionFiles(unittest.TestCase):

    def test_changed_locator_returns_users(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            a = Path(tmpdir) / "a.json"
            _write_actions(a, [["WR_save_test_object",
                                {"test_object_name": "primary_cta",
                                 "object_type": "CSS_SELECTOR"}]])
            b = Path(tmpdir) / "b.json"
            _write_actions(b, [["WR_save_test_object",
                                {"test_object_name": "footer_link",
                                 "object_type": "CSS_SELECTOR"}]])
            index = build_index(tmpdir)
            affected = affected_action_files(index, locators=["primary_cta"])
            self.assertEqual(affected, [str(a)])

    def test_changed_url_substring(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            login = Path(tmpdir) / "login.json"
            _write_actions(login, [["WR_to_url", {"url": "https://example.com/auth/login"}]])
            checkout = Path(tmpdir) / "checkout.json"
            _write_actions(checkout, [["WR_to_url", {"url": "https://example.com/cart"}]])
            index = build_index(tmpdir)
            affected = affected_action_files(index, urls=["/auth/"])
            self.assertEqual(affected, [str(login)])

    def test_multiple_filters_unioned(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            x = Path(tmpdir) / "x.json"
            _write_actions(x, [["WR_render_template", {"template": "login_basic"}]])
            y = Path(tmpdir) / "y.json"
            _write_actions(y, [["WR_save_test_object",
                                {"test_object_name": "footer_link",
                                 "object_type": "ID"}]])
            index = build_index(tmpdir)
            affected = affected_action_files(
                index,
                templates=["login_basic"],
                locators=["footer_link"],
            )
            self.assertEqual(set(affected), {str(x), str(y)})


if __name__ == "__main__":
    unittest.main()
