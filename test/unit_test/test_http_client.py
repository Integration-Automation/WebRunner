import datetime
import unittest
from unittest.mock import MagicMock, patch

from je_web_runner.utils.api.http_client import (
    HttpAssertionError,
    get_last_response,
    http_assert_json_contains,
    http_assert_status,
    http_delete,
    http_get,
    http_post,
    http_request,
    reset_state,
)
from je_web_runner.utils.exception.exceptions import WebRunnerException


def _fake_response(status=200, json_body=None, text="ok"):
    response = MagicMock()
    response.status_code = status
    response.headers = {"X-Test": "1"}
    response.elapsed = datetime.timedelta(milliseconds=42)
    response.text = text
    if json_body is None:
        response.json.side_effect = ValueError("no json")
    else:
        response.json.return_value = json_body
    return response


class TestHttpRequest(unittest.TestCase):

    def setUp(self):
        reset_state()

    def test_get_summarises_response(self):
        with patch("je_web_runner.utils.api.http_client.requests.request",
                   return_value=_fake_response(200, {"hello": "world"})) as request_mock:
            result = http_get("https://api.example/users", params={"q": "a"})
            request_mock.assert_called_once()
            self.assertEqual(result["status_code"], 200)
            self.assertEqual(result["json"], {"hello": "world"})
            self.assertEqual(result["headers"], {"X-Test": "1"})
            self.assertGreaterEqual(result["elapsed_ms"], 42)

    def test_post_passes_json_body(self):
        with patch("je_web_runner.utils.api.http_client.requests.request",
                   return_value=_fake_response(201)) as request_mock:
            http_post("https://api.example/users", json_body={"name": "alice"})
            kwargs = request_mock.call_args.kwargs
            self.assertEqual(kwargs["json"], {"name": "alice"})

    def test_url_must_be_http_or_https(self):
        with self.assertRaises(WebRunnerException):
            http_request("GET", "ftp://example.com")  # NOSONAR — fixture, asserts the validator rejects it
        with self.assertRaises(WebRunnerException):
            http_request("GET", "")

    def test_delete_dispatches_correct_method(self):
        with patch("je_web_runner.utils.api.http_client.requests.request",
                   return_value=_fake_response(204)) as request_mock:
            http_delete("https://api.example/users/1")
            self.assertEqual(request_mock.call_args.args[0], "DELETE")


class TestAssertions(unittest.TestCase):

    def setUp(self):
        reset_state()

    def test_assert_status_matches(self):
        with patch("je_web_runner.utils.api.http_client.requests.request",
                   return_value=_fake_response(200, {"x": 1})):
            http_get("https://api.example/")
        http_assert_status(200)
        with self.assertRaises(HttpAssertionError):
            http_assert_status(500)

    def test_assert_status_without_response_raises(self):
        with self.assertRaises(HttpAssertionError):
            http_assert_status(200)

    def test_assert_json_contains_matches(self):
        with patch("je_web_runner.utils.api.http_client.requests.request",
                   return_value=_fake_response(200, {"name": "alice", "age": 30})):
            http_get("https://api.example/")
        http_assert_json_contains("name", "alice")
        with self.assertRaises(HttpAssertionError):
            http_assert_json_contains("name", "bob")
        with self.assertRaises(HttpAssertionError):
            http_assert_json_contains("missing", "x")

    def test_assert_json_without_json_body(self):
        with patch("je_web_runner.utils.api.http_client.requests.request",
                   return_value=_fake_response(200, json_body=None)):
            http_get("https://api.example/")
        with self.assertRaises(HttpAssertionError):
            http_assert_json_contains("any", "v")

    def test_get_last_response_returns_recorded_state(self):
        with patch("je_web_runner.utils.api.http_client.requests.request",
                   return_value=_fake_response(200, {"a": 1})):
            http_get("https://api.example/")
        snapshot = get_last_response()
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot["json"], {"a": 1})


if __name__ == "__main__":
    unittest.main()
