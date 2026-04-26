import json
import tempfile
import unittest
import urllib.request
from pathlib import Path

from je_web_runner.utils.har_replay import (
    HarReplayError,
    HarReplayServer,
    load_har,
)
from je_web_runner.utils.har_replay.server import HarEntry


def _write_har(path, entries):
    document = {"log": {"entries": entries}}
    Path(path).write_text(json.dumps(document), encoding="utf-8")


class TestLoadHar(unittest.TestCase):

    def test_loads_entries(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            har = Path(tmpdir) / "x.har"
            _write_har(har, [{
                "request": {"method": "GET", "url": "https://api/foo"},
                "response": {
                    "status": 200,
                    "headers": [{"name": "Content-Type", "value": "application/json"}],
                    "content": {"text": '{"ok": true}', "mimeType": "application/json"},
                },
            }])
            entries = load_har(har)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0].path, "/foo")
            self.assertEqual(entries[0].body, '{"ok": true}')

    def test_missing_file_raises(self):
        with self.assertRaises(HarReplayError):
            load_har("nope.har")

    def test_invalid_json_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            har = Path(tmpdir) / "x.har"
            har.write_text("not json", encoding="utf-8")
            with self.assertRaises(HarReplayError):
                load_har(har)

    def test_missing_log_entries_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            har = Path(tmpdir) / "x.har"
            har.write_text(json.dumps({"log": {}}), encoding="utf-8")
            with self.assertRaises(HarReplayError):
                load_har(har)

    def test_url_query_string_kept(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            har = Path(tmpdir) / "x.har"
            _write_har(har, [{
                "request": {"method": "GET", "url": "https://api/foo?id=42"},
                "response": {"status": 200, "content": {"text": ""}},
            }])
            entries = load_har(har)
            self.assertEqual(entries[0].path, "/foo?id=42")


class TestHarReplayServerMatching(unittest.TestCase):

    def test_exact_match(self):
        server = HarReplayServer(entries=[HarEntry(
            method="GET", path="/api", status=200, body="ok",
        )])
        match = server.find("GET", "/api")
        self.assertIsNotNone(match)

    def test_method_filter(self):
        server = HarReplayServer(entries=[HarEntry(
            method="POST", path="/x", status=200,
        )])
        self.assertIsNone(server.find("GET", "/x"))

    def test_glob_match(self):
        server = HarReplayServer(entries=[HarEntry(
            method="GET", path="/api/users/*", status=200,
        )])
        self.assertIsNotNone(server.find("GET", "/api/users/42"))

    def test_regex_match(self):
        server = HarReplayServer(entries=[HarEntry(
            method="POST", path="re:/api/v\\d+/items", status=201,
        )])
        self.assertIsNotNone(server.find("POST", "/api/v3/items"))

    def test_rotation_then_sticky(self):
        server = HarReplayServer(entries=[
            HarEntry(method="GET", path="/x", status=200, body="first"),
            HarEntry(method="GET", path="/x", status=200, body="second"),
        ])
        self.assertEqual(server.find("GET", "/x").body, "first")
        self.assertEqual(server.find("GET", "/x").body, "second")
        self.assertEqual(server.find("GET", "/x").body, "second")

    def test_calls_recorded(self):
        server = HarReplayServer(entries=[HarEntry(method="GET", path="/x", status=200)])
        server.find("GET", "/x")
        server.find("POST", "/y")
        self.assertEqual(server.calls, [("GET", "/x"), ("POST", "/y")])

    def test_empty_entries_raises(self):
        with self.assertRaises(HarReplayError):
            HarReplayServer(entries=[])


class TestHttpServer(unittest.TestCase):

    def test_serves_recorded_response(self):
        server = HarReplayServer(entries=[HarEntry(
            method="GET", path="/foo", status=200,
            headers={"Content-Type": "application/json"},
            body='{"ok": true}',
        )])
        url = server.start()
        try:
            with urllib.request.urlopen(url + "/foo", timeout=2) as response:  # nosec B310
                body = response.read().decode("utf-8")
                self.assertEqual(response.status, 200)
            self.assertEqual(body, '{"ok": true}')
        finally:
            server.stop()

    def test_unmatched_returns_404(self):
        server = HarReplayServer(entries=[HarEntry(method="GET", path="/foo", status=200)])
        url = server.start()
        try:
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(url + "/missing", timeout=2)  # nosec B310
            self.assertEqual(ctx.exception.code, 404)
        finally:
            server.stop()


if __name__ == "__main__":
    unittest.main()
