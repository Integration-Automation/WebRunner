import os
import tempfile
import unittest
from pathlib import Path

from je_web_runner.utils.extensions.extension_loader import (
    ExtensionLoaderError,
    playwright_extension_launch_args,
    selenium_chrome_options_with_extension,
)


class TestSeleniumExtensionLoader(unittest.TestCase):

    def test_crx_file_uses_add_extension(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            crx = os.path.join(tmpdir, "extension.crx")
            Path(crx).write_bytes(b"\x00\x00\x00\x00")
            options = selenium_chrome_options_with_extension(crx)
            # ChromeOptions stores .crx as encoded extensions list.
            self.assertTrue(options.extensions or options.arguments)

    def test_unpacked_dir_uses_load_extension_argument(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            options = selenium_chrome_options_with_extension(tmpdir)
            self.assertTrue(any(arg.startswith("--load-extension=") for arg in options.arguments))

    def test_missing_path_raises(self):
        with self.assertRaises(ExtensionLoaderError):
            selenium_chrome_options_with_extension("/no/such/path")


class TestPlaywrightExtensionArgs(unittest.TestCase):

    def test_returns_two_args(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            args = playwright_extension_launch_args(tmpdir)
            self.assertEqual(len(args), 2)
            self.assertTrue(any(arg.startswith("--disable-extensions-except=") for arg in args))
            self.assertTrue(any(arg.startswith("--load-extension=") for arg in args))

    def test_file_input_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            crx = os.path.join(tmpdir, "x.crx")
            Path(crx).write_bytes(b"\x00")
            with self.assertRaises(ExtensionLoaderError):
                playwright_extension_launch_args(crx)


if __name__ == "__main__":
    unittest.main()
