import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from je_web_runner.utils.file_transfer.file_helpers import (
    FileTransferError,
    list_new_downloads,
    playwright_upload_file,
    selenium_upload_file,
    snapshot_directory,
    wait_for_download,
)


class TestUpload(unittest.TestCase):

    def test_selenium_upload_sends_keys(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "data.csv")
            Path(target).write_text("a,b\n1,2\n", encoding="utf-8")
            with patch("je_web_runner.utils.file_transfer.file_helpers.webdriver_wrapper_instance") as wrapper:
                driver = MagicMock()
                wrapper.current_webdriver = driver
                element = MagicMock()
                driver.find_element.return_value = element
                selenium_upload_file("input[name=upload]", target)
                element.send_keys.assert_called_once()

    def test_selenium_missing_file_raises(self):
        with self.assertRaises(FileTransferError):
            selenium_upload_file("input", "/no/such/file.csv")

    def test_playwright_upload_calls_set_input_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "x.png")
            Path(target).write_bytes(b"\x89PNG")
            with patch("je_web_runner.utils.file_transfer.file_helpers.playwright_wrapper_instance") as wrapper:
                page = MagicMock()
                wrapper.page = page
                playwright_upload_file("#upload", target)
                page.set_input_files.assert_called_once()


class TestDownload(unittest.TestCase):

    def test_wait_for_download_returns_new_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            initial = os.path.join(tmpdir, "old.txt")
            Path(initial).write_text("seen", encoding="utf-8")
            target = os.path.join(tmpdir, "report.csv")

            # Drop the new file shortly after wait_for_download starts so
            # the snapshot captures only ``old.txt``.
            def _drop_file_later():
                time.sleep(0.1)
                Path(target).write_text("done", encoding="utf-8")

            threading.Thread(target=_drop_file_later, daemon=True).start()
            result = wait_for_download(tmpdir, timeout=3.0, poll_seconds=0.05)
            self.assertEqual(result, str(Path(target).resolve()))

    def test_wait_for_download_skips_partials(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            partial = os.path.join(tmpdir, "x.crdownload")
            Path(partial).write_text("incomplete", encoding="utf-8")
            with self.assertRaises(FileTransferError):
                wait_for_download(tmpdir, timeout=0.2, poll_seconds=0.05)

    def test_wait_for_download_suffix_filter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            other = os.path.join(tmpdir, "other.txt")
            Path(other).write_text("nope", encoding="utf-8")
            csv_path = os.path.join(tmpdir, "ok.csv")

            def _drop_csv_later():
                time.sleep(0.1)
                Path(csv_path).write_text("yes", encoding="utf-8")

            threading.Thread(target=_drop_csv_later, daemon=True).start()
            result = wait_for_download(tmpdir, timeout=3.0, suffix=".csv", poll_seconds=0.05)
            self.assertTrue(result.endswith("ok.csv"))

    def test_list_new_downloads_diff(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            existing = os.path.join(tmpdir, "old.txt")
            Path(existing).write_text("a", encoding="utf-8")
            before = snapshot_directory(tmpdir)
            new_file = os.path.join(tmpdir, "new.bin")
            Path(new_file).write_bytes(b"\x00")
            new = list_new_downloads(tmpdir, before)
            self.assertEqual(len(new), 1)
            self.assertTrue(new[0].endswith("new.bin"))


if __name__ == "__main__":
    unittest.main()
