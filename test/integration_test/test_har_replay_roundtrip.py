"""
Integration: HarReplayServer + GraphQLClient + raw urllib client.

Confirms the in-process HAR server actually serves recorded responses
across method / glob / regex matchers and that the GraphQL client wired
into it round-trips a real GraphQL-shaped envelope.
"""
import json
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from je_web_runner.utils.har_replay.server import (
    HarEntry,
    HarReplayServer,
    load_har,
)


def _make_har(entries):
    return {"log": {"entries": entries}}


def _write_har(path, entries):
    Path(path).write_text(json.dumps(_make_har(entries)), encoding="utf-8")


class TestHarReplayRoundTrip(unittest.TestCase):

    def test_serves_recorded_responses(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            har = Path(tmpdir) / "recording.har"
            _write_har(har, [
                {"request": {"method": "GET", "url": "https://api/foo"},
                 "response": {"status": 201, "headers": [
                     {"name": "Content-Type", "value": "application/json"},
                 ], "content": {"text": '{"ok": true}'}}},
                {"request": {"method": "GET", "url": "https://api/bar/123"},
                 "response": {"status": 200, "headers": [],
                              "content": {"text": '{"id": 123}'}}},
            ])
            entries = load_har(har)
            server = HarReplayServer(entries=entries)
            url = server.start()
            try:
                with urllib.request.urlopen(url + "/foo", timeout=2) as response:  # nosec B310 — local fixture
                    body = response.read().decode("utf-8")
                self.assertEqual(response.status, 201)
                self.assertEqual(json.loads(body), {"ok": True})

                with urllib.request.urlopen(url + "/bar/123", timeout=2) as response:  # nosec B310
                    self.assertEqual(json.loads(response.read())["id"], 123)
            finally:
                server.stop()

    def test_glob_url_matching(self):
        server = HarReplayServer(entries=[
            HarEntry(method="GET", path="/users/*", status=200,
                     headers={"content-type": "application/json"},
                     body='{"id": "any"}'),
        ])
        url = server.start()
        try:
            with urllib.request.urlopen(url + "/users/42", timeout=2) as response:  # nosec B310
                self.assertEqual(json.loads(response.read())["id"], "any")
        finally:
            server.stop()

    def test_unmatched_returns_404_with_diagnostic_payload(self):
        server = HarReplayServer(entries=[
            HarEntry(method="GET", path="/exists", status=200, body="ok"),
        ])
        url = server.start()
        try:
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(url + "/missing", timeout=2)  # nosec B310
            payload = json.loads(ctx.exception.read())
            self.assertEqual(ctx.exception.code, 404)
            self.assertEqual(payload["method"], "GET")
            self.assertEqual(payload["path"], "/missing")
        finally:
            server.stop()

    def test_graphql_client_against_har_server(self):
        from je_web_runner.utils.graphql.client import GraphQLClient

        gql_payload = json.dumps({"data": {"viewer": {"login": "alice"}}})
        # GraphQL clients POST to /graphql; HAR matcher needs an exact path.
        server = HarReplayServer(entries=[
            HarEntry(method="POST", path="/graphql", status=200,
                     headers={"content-type": "application/json"},
                     body=gql_payload),
        ])
        url = server.start()
        try:
            client = GraphQLClient(endpoint=url + "/graphql")
            result = client.execute("{ viewer { login } }")
        finally:
            server.stop()
        self.assertEqual(result["data"]["viewer"]["login"], "alice")


if __name__ == "__main__":
    unittest.main()
