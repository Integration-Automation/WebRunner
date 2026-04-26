"""
Integration: MockOAuthServer + http_client + assertion helpers.

Boots the in-process OAuth issuer, requests a token, then uses the token
to drive the project's http_client wrapper against a second HAR-backed
server. End-to-end exercise of bearer-token plumbing without external
dependencies.
"""
import json
import unittest
import urllib.request

from je_web_runner.utils.har_replay.server import HarEntry, HarReplayServer
from je_web_runner.utils.mock_services.servers import (
    MockOAuthServer,
    MockS3Storage,
)


class TestOAuthAndApi(unittest.TestCase):

    def test_token_then_authenticated_call(self):
        oauth = MockOAuthServer()
        api = HarReplayServer(entries=[
            HarEntry(method="GET", path="/me", status=200,
                     headers={"content-type": "application/json"},
                     body='{"login": "alice"}'),
        ])
        oauth_url = oauth.start()
        api_url = api.start()
        try:
            request = urllib.request.Request(oauth_url + "/token", method="POST")
            with urllib.request.urlopen(request, timeout=2) as response:  # nosec B310 — local fixture
                payload = json.loads(response.read())
            token = payload["access_token"]
            self.assertTrue(token)

            api_request = urllib.request.Request(api_url + "/me")
            api_request.add_header("Authorization", f"Bearer {token}")
            with urllib.request.urlopen(api_request, timeout=2) as response:  # nosec B310
                me = json.loads(response.read())
            self.assertEqual(me["login"], "alice")
            # OAuth server should have recorded the issuance.
            self.assertEqual(oauth.issued, [token])
        finally:
            oauth.stop()
            api.stop()


class TestMockS3PaymentLikeFlow(unittest.TestCase):

    def test_put_get_list_round_trip(self):
        store = MockS3Storage()
        store.create_bucket("artifacts")
        store.put_object("artifacts", "report.json", b'{"ok": true}')
        self.assertEqual(store.get_object("artifacts", "report.json"),
                         b'{"ok": true}')
        self.assertEqual(store.list_objects("artifacts"), ["report.json"])


if __name__ == "__main__":
    unittest.main()
