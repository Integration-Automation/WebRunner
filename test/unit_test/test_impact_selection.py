"""Impact-based selection: --affected-by, @files, --changed-since (fake and real git), the CLI."""
import json
import os
import shutil
import subprocess  # nosec B404 — fixed git commands in a scratch repository
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from je_web_runner.utils.cli.cli_main import main
from je_web_runner.utils.impact_analysis.indexer import ImpactAnalysisError
from je_web_runner.utils.impact_analysis.selection import parse_affected, select_by_impact

_SETUP = [["WR_save_test_object", {"test_object_name": "login_button", "object_type": "ID"}]]
_LOGIN = [["WR_to_url", {"url": "https://shop.test/login"}],
          ["WR_find_recorded_element", {"element_name": "login_button"}], ["WR_element_click"]]
_SEARCH = [["WR_to_url", {"url": "https://shop.test/search"}], ["WR_render_template", {"template": "close_modal"}]]
_CART = [["WR_to_url", {"url": "https://shop.test/cart"}], ["WR_quit"]]


def _write(directory: Path, name: str, actions) -> str:
    path = directory / name
    path.write_text(json.dumps(actions), encoding="utf-8")
    return os.path.abspath(path)


class _Suite(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.dir = self.root / "actions"
        self.dir.mkdir()
        self.setup = _write(self.dir, "setup.json", _SETUP)
        self.login = _write(self.dir, "login.json", _LOGIN)
        self.search = _write(self.dir, "search.json", _SEARCH)
        self.cart = _write(self.dir, "cart.json", _CART)
        self.files = [self.cart, self.login, self.search, self.setup]


class TestAffectedBy(_Suite):

    def test_each_kind(self):
        def pick(*specs):
            return select_by_impact(self.files, str(self.dir), affected_by=specs)
        self.assertEqual(pick("locator:login_button"), [self.login, self.setup])
        self.assertEqual(pick("url:/cart"), [self.cart])
        self.assertEqual(pick("template:close_modal"), [self.search])
        self.assertEqual(pick("command:WR_quit", "url:/search"), [self.cart, self.search])
        self.assertEqual(pick("locator:nobody_uses_this"), [])

    def test_a_list_file_with_comments(self):
        listing = self.root / "affected.txt"
        listing.write_text("# from the CI step\n\nurl:/cart\n template:close_modal \n", encoding="utf-8")
        self.assertEqual(parse_affected([f"@{listing}"])["template"], ["close_modal"])
        self.assertEqual(select_by_impact(self.files, str(self.dir), affected_by=[f"@{listing}"]),
                         [self.cart, self.search])

    def test_bad_specs(self):
        for spec in ("login_button", "selector:#x", "url:", f"@{self.root / 'missing.txt'}"):
            with self.subTest(spec=spec), self.assertRaises(ImpactAnalysisError):
                parse_affected([spec])


class TestChangedSince(_Suite):

    def _git(self, changed):
        def run(args):
            if args[:2] == ["rev-parse", "--show-toplevel"]:
                return str(self.root) + "\n"
            self.assertEqual(args, ["diff", "--name-only", "main...HEAD"])
            return "\n".join(changed) + "\n"
        return run

    def test_a_changed_setup_pulls_in_the_tests_sharing_its_locator(self):
        selected = select_by_impact(self.files, str(self.dir), changed_since="main",
                                    git_runner=self._git(["actions/setup.json", "README.md"]))
        self.assertEqual(selected, [self.login, self.setup])

    def test_urls_and_commands_are_not_followed(self):
        selected = select_by_impact(self.files, str(self.dir), changed_since="main",
                                    git_runner=self._git(["actions/cart.json"]))
        self.assertEqual(selected, [self.cart])

    def test_combined_with_affected_by(self):
        selected = select_by_impact(self.files, str(self.dir), affected_by=["template:close_modal"],
                                    changed_since="main", git_runner=self._git(["actions/cart.json"]))
        self.assertEqual(selected, [self.cart, self.search])


class TestCli(_Suite):

    def _ran(self, *flags):
        with patch("je_web_runner.utils.cli.cli_main.execute_files") as run:
            main(["-d", str(self.dir), *flags])
        return sorted(run.call_args.args[0]) if run.called else []

    def test_affected_by_with_a_cache_and_tags_still_applying_after(self):
        cache = self.root / "impact.json"
        self.assertEqual(self._ran("--affected-by", "locator:login_button", "--impact-cache", str(cache)),
                         sorted([self.login, self.setup]))
        self.assertTrue(cache.is_file())
        self.assertEqual(self._ran("--affected-by", "locator:login_button", "--shard", "1/1"),
                         sorted([self.login, self.setup]))

    @unittest.skipIf(shutil.which("git") is None, "git is not installed")
    def test_changed_since_against_a_real_repository(self):
        def git(*args):
            subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True)  # nosec B603 B607
        git("init", "-q", "-b", "main")
        git("-c", "user.name=t", "-c", "user.email=t@t", "add", ".")
        git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "base")
        git("checkout", "-q", "-b", "change")
        _write(self.dir, "setup.json", _SETUP + [["WR_implicitly_wait", {"time_to_wait": 2}]])
        git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-am", "change setup")
        previous = os.getcwd()
        os.chdir(self.root)  # git diff runs in the current directory, as it does for a CLI user
        self.addCleanup(os.chdir, previous)
        self.assertEqual(self._ran("--changed-since", "main"), sorted([self.login, self.setup]))


if __name__ == "__main__":
    unittest.main()
