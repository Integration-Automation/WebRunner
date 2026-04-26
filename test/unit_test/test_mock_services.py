import json
import unittest
import urllib.request

from je_web_runner.utils.mock_services import (
    MockOAuthServer,
    MockS3Storage,
    MockServiceError,
)


class TestMockS3Storage(unittest.TestCase):

    def test_round_trip(self):
        storage = MockS3Storage()
        storage.create_bucket("artifacts")
        storage.put_object("artifacts", "report.json", b"{}")
        self.assertEqual(storage.get_object("artifacts", "report.json"), b"{}")
        self.assertEqual(storage.list_objects("artifacts"), ["report.json"])

    def test_missing_bucket_raises(self):
        storage = MockS3Storage()
        with self.assertRaises(MockServiceError):
            storage.put_object("nope", "k", b"v")

    def test_missing_object_raises(self):
        storage = MockS3Storage()
        storage.create_bucket("b")
        with self.assertRaises(MockServiceError):
            storage.get_object("b", "missing")

    def test_non_bytes_body_rejected(self):
        storage = MockS3Storage()
        storage.create_bucket("b")
        with self.assertRaises(MockServiceError):
            storage.put_object("b", "k", "string-not-bytes")  # type: ignore[arg-type]


class TestMockOAuthServer(unittest.TestCase):

    def test_issues_bearer_token(self):
        server = MockOAuthServer()
        url = server.start()
        try:
            request = urllib.request.Request(url + "/token", data=b"", method="POST")
            with urllib.request.urlopen(request, timeout=2) as response:  # nosec B310
                payload = json.loads(response.read())
            self.assertEqual(payload["token_type"], "Bearer")
            self.assertTrue(payload["access_token"])
            self.assertEqual(server.issued[-1], payload["access_token"])
        finally:
            server.stop()

    def test_unknown_path_404(self):
        server = MockOAuthServer()
        url = server.start()
        try:
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(  # nosec B310
                    urllib.request.Request(url + "/wat", data=b"", method="POST"),
                    timeout=2,
                )
            self.assertEqual(ctx.exception.code, 404)
        finally:
            server.stop()

    def test_double_start_rejected(self):
        server = MockOAuthServer()
        server.start()
        try:
            with self.assertRaises(MockServiceError):
                server.start()
        finally:
            server.stop()


if __name__ == "__main__":
    unittest.main()
