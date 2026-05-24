"""Unit tests for je_web_runner.utils.webhook_receiver."""
import json
import unittest
from urllib.request import Request, urlopen

from je_web_runner.utils.webhook_receiver.receiver import (
    ReceivedRequest,
    WebhookReceiverError,
    WebhookServer,
    assert_received_json_matching,
    assert_received_path,
    assert_received_with_header,
)


def _post(url, body=b"", headers=None):
    req = Request(url, data=body, headers=headers or {}, method="POST")
    with urlopen(req, timeout=5) as response:
        return response.status, response.read()


def _get(url):
    with urlopen(url, timeout=5) as response:
        return response.status, response.read()


class TestWebhookServer(unittest.TestCase):

    def test_starts_and_stops(self):
        with WebhookServer() as server:
            self.assertTrue(server.base_url.startswith("http://127.0.0.1:"))
            status, _ = _get(server.base_url + "/ping")
            self.assertEqual(status, 200)

    def test_captures_post_body(self):
        with WebhookServer() as server:
            _post(
                server.base_url + "/hooks/order",
                body=json.dumps({"id": 42}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            requests = server.received()
            self.assertEqual(len(requests), 1)
            self.assertEqual(requests[0].path, "/hooks/order")
            self.assertEqual(requests[0].method, "POST")
            self.assertEqual(requests[0].body_json(), {"id": 42})

    def test_query_parsed(self):
        with WebhookServer() as server:
            _get(server.base_url + "/x?a=1&a=2&b=3")
            request = server.received()[0]
            self.assertEqual(request.query["a"], ["1", "2"])
            self.assertEqual(request.query["b"], ["3"])

    def test_clear(self):
        with WebhookServer() as server:
            _get(server.base_url + "/x")
            server.clear()
            self.assertEqual(server.received(), [])

    def test_custom_response(self):
        def resp(req):
            return {"status": 201, "body": b"created"}
        with WebhookServer(response_fn=resp) as server:
            status, body = _post(server.base_url + "/x")
            self.assertEqual(status, 201)
            self.assertEqual(body, b"created")

    def test_wait_for(self):
        with WebhookServer() as server:
            _post(server.base_url + "/expected")
            request = server.wait_for(lambda r: r.path == "/expected", timeout=1.0)
            self.assertEqual(request.path, "/expected")

    def test_wait_for_timeout(self):
        with WebhookServer() as server:
            with self.assertRaises(WebhookReceiverError):
                server.wait_for(lambda r: r.path == "/never", timeout=0.2)

    def test_wait_for_bad_args(self):
        with WebhookServer() as server:
            with self.assertRaises(WebhookReceiverError):
                server.wait_for(lambda r: True, timeout=0)
            with self.assertRaises(WebhookReceiverError):
                server.wait_for(lambda r: True, timeout=1, interval=0)

    def test_double_start_rejected(self):
        server = WebhookServer().start()
        try:
            with self.assertRaises(WebhookReceiverError):
                server.start()
        finally:
            server.stop()

    def test_bad_host(self):
        with self.assertRaises(WebhookReceiverError):
            WebhookServer(host="")

    def test_bad_port(self):
        with self.assertRaises(WebhookReceiverError):
            WebhookServer(port=0)
        with self.assertRaises(WebhookReceiverError):
            WebhookServer(port=99999)


class TestReceivedRequest(unittest.TestCase):

    def test_body_text(self):
        request = ReceivedRequest(method="POST", path="/", body=b"hi")
        self.assertEqual(request.body_text(), "hi")

    def test_body_json_bad(self):
        request = ReceivedRequest(method="POST", path="/", body=b"not json")
        with self.assertRaises(WebhookReceiverError):
            request.body_json()

    def test_to_dict(self):
        request = ReceivedRequest(method="POST", path="/", body=b"hi")
        self.assertEqual(request.to_dict()["body"], "hi")


class TestAssertions(unittest.TestCase):

    def test_assert_received_path(self):
        with WebhookServer() as server:
            _post(server.base_url + "/x")
            _post(server.base_url + "/x")
            self.assertEqual(assert_received_path(server, "/x", minimum=2), 2)

    def test_assert_received_path_method_filter(self):
        with WebhookServer() as server:
            _get(server.base_url + "/x")
            self.assertEqual(
                assert_received_path(server, "/x", method="GET"), 1,
            )

    def test_assert_received_path_fail(self):
        with WebhookServer() as server:
            with self.assertRaises(WebhookReceiverError):
                assert_received_path(server, "/missing")

    def test_assert_received_path_empty(self):
        with WebhookServer() as server:
            with self.assertRaises(WebhookReceiverError):
                assert_received_path(server, "")

    def test_assert_received_with_header(self):
        with WebhookServer() as server:
            _post(
                server.base_url + "/x",
                headers={"X-Token": "abc123"},
            )
            request = assert_received_with_header(server, "X-Token", "abc123")
            self.assertEqual(request.path, "/x")

    def test_assert_received_with_header_miss(self):
        with WebhookServer() as server:
            _post(server.base_url + "/x")
            with self.assertRaises(WebhookReceiverError):
                assert_received_with_header(server, "X-Missing", "x")

    def test_assert_received_with_header_empty(self):
        with WebhookServer() as server:
            with self.assertRaises(WebhookReceiverError):
                assert_received_with_header(server, "", "x")

    def test_assert_received_json_matching(self):
        with WebhookServer() as server:
            _post(
                server.base_url + "/x",
                body=json.dumps({"event": "order.created"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            request = assert_received_json_matching(
                server, lambda p: p.get("event") == "order.created",
            )
            self.assertEqual(request.path, "/x")

    def test_assert_received_json_matching_miss(self):
        with WebhookServer() as server:
            _post(server.base_url + "/x", body=b"not json")
            with self.assertRaises(WebhookReceiverError):
                assert_received_json_matching(server, lambda p: True)


if __name__ == "__main__":
    unittest.main()
