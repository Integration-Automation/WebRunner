import tempfile
import unittest
from pathlib import Path

from je_web_runner.utils.bootstrapper import (
    BootstrapError,
    init_workspace,
    starter_files,
)


class TestBootstrapper(unittest.TestCase):

    def test_creates_all_starter_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report = init_workspace(tmpdir)
            for entry in starter_files():
                self.assertTrue(
                    (Path(tmpdir) / entry.relative_path).is_file(),
                    msg=f"{entry.relative_path} not created",
                )
            self.assertTrue(all(state == "created" for state in report.values()))

    def test_skips_existing_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            init_workspace(tmpdir)
            (Path(tmpdir) / "README.md").write_text("custom", encoding="utf-8")
            report = init_workspace(tmpdir, overwrite=False)
            self.assertEqual(report["README.md"], "skipped")
            self.assertEqual((Path(tmpdir) / "README.md").read_text(), "custom")

    def test_overwrite_replaces(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            init_workspace(tmpdir)
            (Path(tmpdir) / "README.md").write_text("custom", encoding="utf-8")
            init_workspace(tmpdir, overwrite=True)
            actual = (Path(tmpdir) / "README.md").read_text(encoding="utf-8")
            self.assertNotEqual(actual, "custom")

    def test_target_not_dir_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "f.txt"
            target.write_text("file", encoding="utf-8")
            with self.assertRaises(BootstrapError):
                init_workspace(str(target))

    def test_starter_includes_workflow(self):
        paths = [f.relative_path for f in starter_files()]
        self.assertIn(".github/workflows/webrunner.yml", paths)
        self.assertIn(".webrunner/drivers.json", paths)
        self.assertIn("actions/sample.json", paths)


if __name__ == "__main__":
    unittest.main()
