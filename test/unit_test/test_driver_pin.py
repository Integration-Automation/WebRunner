import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from je_web_runner.utils.driver_pin import (
    DriverPinError,
    PinnedDriver,
    download_pinned,
    load_pinfile,
    save_pinfile,
)
from je_web_runner.utils.driver_pin.pinner import (
    install_for_browser,
)


def _zip_with(filename, content=b"fake-binary"):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr(filename, content)
    return buffer.getvalue()


class TestPinFile(unittest.TestCase):

    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "drivers.json"
            drivers = [PinnedDriver(
                name="geckodriver",
                version="0.34.0",
                url="https://example.com/g.zip",
                archive_format="zip",
                binary_inside="geckodriver.exe",
                platforms=["win"],
            )]
            save_pinfile(path, drivers)
            loaded = load_pinfile(path)
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0].version, "0.34.0")

    def test_missing_file(self):
        with self.assertRaises(DriverPinError):
            load_pinfile("nope.json")

    def test_invalid_archive_format(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "x.json"
            path.write_text(json.dumps({"drivers": [{
                "name": "g", "version": "1", "url": "https://x", "archive_format": "rar",
                "binary_inside": "g",
            }]}), encoding="utf-8")
            with self.assertRaises(DriverPinError):
                load_pinfile(path)

    def test_non_http_url_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "x.json"
            path.write_text(json.dumps({"drivers": [{
                "name": "g", "version": "1", "url": "ftp://x", "archive_format": "zip",
                "binary_inside": "g",
            }]}), encoding="utf-8")
            with self.assertRaises(DriverPinError):
                load_pinfile(path)


class TestDownloadPinned(unittest.TestCase):

    def test_uses_cache_when_present(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "cache"
            target = cache_dir / "geckodriver/0.34.0/geckodriver.exe"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"existing")
            pinned = PinnedDriver(
                name="geckodriver", version="0.34.0",
                url="https://example.com/g.zip",
                archive_format="zip",
                binary_inside="geckodriver.exe",
            )
            calls = []
            result = download_pinned(
                pinned, cache_dir=cache_dir,
                fetch=lambda url: (calls.append(url), b"")[1],
            )
            self.assertEqual(result, target)
            self.assertEqual(calls, [])  # cached, no fetch

    def test_extracts_zip_archive(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "cache"
            payload = _zip_with("geckodriver.exe")
            pinned = PinnedDriver(
                name="geckodriver", version="0.34.0",
                url="https://example.com/g.zip",
                archive_format="zip",
                binary_inside="geckodriver.exe",
            )
            result = download_pinned(pinned, cache_dir=cache_dir,
                                     fetch=lambda _url: payload)
            self.assertTrue(result.is_file())
            self.assertEqual(result.read_bytes(), b"fake-binary")

    def test_missing_binary_in_archive_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "cache"
            payload = _zip_with("not-the-binary.txt")
            pinned = PinnedDriver(
                name="geckodriver", version="0.34.0",
                url="https://example.com/g.zip",
                archive_format="zip",
                binary_inside="geckodriver.exe",
            )
            with self.assertRaises(DriverPinError):
                download_pinned(pinned, cache_dir=cache_dir,
                                fetch=lambda _url: payload)

    def test_empty_payload_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "cache"
            pinned = PinnedDriver(
                name="g", version="1", url="https://x", archive_format="zip",
                binary_inside="g",
            )
            with self.assertRaises(DriverPinError):
                download_pinned(pinned, cache_dir=cache_dir,
                                fetch=lambda _url: b"")


class TestInstallForBrowser(unittest.TestCase):

    def test_picks_matching_platform(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pin_file = Path(tmpdir) / "drivers.json"
            payload = _zip_with("geckodriver.exe")
            save_pinfile(pin_file, [PinnedDriver(
                name="geckodriver", version="0.34.0",
                url="https://example.com/g.zip",
                archive_format="zip",
                binary_inside="geckodriver.exe",
                platforms=[],  # an empty list means match every platform
            )])
            cache_dir = Path(tmpdir) / "cache"
            result = install_for_browser(
                pin_file, "firefox",
                cache_dir=cache_dir,
                fetch=lambda _url: payload,
            )
            self.assertIsNotNone(result)
            self.assertTrue(result.is_file())

    def test_no_match_returns_none(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pin_file = Path(tmpdir) / "drivers.json"
            save_pinfile(pin_file, [])
            self.assertIsNone(install_for_browser(pin_file, "firefox"))


if __name__ == "__main__":
    unittest.main()
