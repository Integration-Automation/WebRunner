import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from je_web_runner.utils.extension_harness import (
    ExtensionHarnessError,
    apply_to_chrome_options,
    extension_info,
    parse_manifest,
    playwright_persistent_context_args,
)


def _write_manifest(directory, manifest):
    Path(directory).mkdir(parents=True, exist_ok=True)
    (Path(directory) / "manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )


class TestParseManifest(unittest.TestCase):

    def test_mv3_action(self):
        info = parse_manifest({
            "name": "Sample",
            "version": "1.0",
            "manifest_version": 3,
            "action": {"default_popup": "popup.html"},
            "background": {"service_worker": "bg.js"},
            "permissions": ["storage"],
        })
        self.assertEqual(info.name, "Sample")
        self.assertEqual(info.popup, "popup.html")
        self.assertEqual(info.background_script, "bg.js")
        self.assertEqual(info.permissions, ["storage"])

    def test_mv2_browser_action(self):
        info = parse_manifest({
            "name": "Old",
            "version": "0.5",
            "manifest_version": 2,
            "browser_action": {"default_popup": "popup.html"},
            "background": {"scripts": ["bg.js"]},
        })
        self.assertEqual(info.popup, "popup.html")
        self.assertEqual(info.background_script, "bg.js")

    def test_invalid_manifest_version(self):
        with self.assertRaises(ExtensionHarnessError):
            parse_manifest({"name": "x", "version": "1", "manifest_version": 1})

    def test_missing_name(self):
        with self.assertRaises(ExtensionHarnessError):
            parse_manifest({"version": "1", "manifest_version": 3})

    def test_path_input(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_manifest(tmpdir, {
                "name": "X", "version": "1.0", "manifest_version": 3,
            })
            info = parse_manifest(tmpdir)
            self.assertEqual(info.name, "X")

    def test_missing_path_raises(self):
        with self.assertRaises(ExtensionHarnessError):
            parse_manifest("not-a-real-dir")

    def test_extension_info_stamps_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_manifest(tmpdir, {
                "name": "X", "version": "1.0", "manifest_version": 3,
            })
            info = extension_info(tmpdir)
            self.assertEqual(info.extension_dir, str(Path(tmpdir).resolve()))


class TestApplyToChromeOptions(unittest.TestCase):

    def test_adds_args(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_manifest(tmpdir, {
                "name": "X", "version": "1.0", "manifest_version": 3,
            })
            options = MagicMock()
            apply_to_chrome_options(options, [tmpdir])
            args = [c.args[0] for c in options.add_argument.call_args_list]
            self.assertTrue(any(a.startswith("--load-extension=") for a in args))
            self.assertTrue(any(a.startswith("--disable-extensions-except=")
                                for a in args))

    def test_missing_dir_raises(self):
        options = MagicMock()
        with self.assertRaises(ExtensionHarnessError):
            apply_to_chrome_options(options, ["./does-not-exist"])

    def test_invalid_options_object_raises(self):
        with self.assertRaises(ExtensionHarnessError):
            apply_to_chrome_options(object(), [])


class TestPlaywrightArgs(unittest.TestCase):

    def test_returns_persistent_args(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ext = Path(tmpdir) / "ext"
            _write_manifest(ext, {
                "name": "X", "version": "1.0", "manifest_version": 3,
            })
            user_data = Path(tmpdir) / "userdata"
            args = playwright_persistent_context_args(
                [ext], user_data, headless=False,
            )
            self.assertEqual(args["user_data_dir"], str(user_data))
            self.assertFalse(args["headless"])
            joined = " ".join(args["args"])
            self.assertIn("--load-extension=", joined)


if __name__ == "__main__":
    unittest.main()
