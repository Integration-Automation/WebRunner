import io
import json
import unittest
from unittest.mock import patch

from je_web_runner.utils.graphql import (
    GraphQLClient,
    GraphQLError,
    extract_field,
    introspect_types,
)


def _fake_response(payload):
    body = json.dumps(payload).encode("utf-8")
    fake = io.BytesIO(body)
    fake.__enter__ = lambda self=fake: self
    fake.__exit__ = lambda *args: None
    return fake


class TestExtractField(unittest.TestCase):

    def test_simple_path(self):
        payload = {"data": {"user": {"name": "Alice"}}}
        self.assertEqual(extract_field(payload, "user.name"), "Alice")

    def test_index(self):
        payload = {"data": {"users": [{"id": 1}, {"id": 2}]}}
        self.assertEqual(extract_field(payload, "users[1].id"), 2)

    def test_missing_field_raises(self):
        with self.assertRaises(GraphQLError):
            extract_field({"data": {}}, "missing")


class TestGraphQLClient(unittest.TestCase):

    def test_invalid_endpoint_rejected(self):
        with self.assertRaises(GraphQLError):
            GraphQLClient("ftp://example.com")

    def test_executes_query(self):
        client = GraphQLClient("https://api.example.com/graphql")
        with patch(
            "je_web_runner.utils.graphql.client.urllib.request.urlopen",
            return_value=_fake_response({"data": {"ok": True}}),
        ) as urlopen_mock:
            result = client.execute("{ ok }")
        self.assertEqual(result["data"]["ok"], True)
        urlopen_mock.assert_called_once()

    def test_errors_in_payload_raise(self):
        client = GraphQLClient("https://api.example.com/graphql")
        with patch(
            "je_web_runner.utils.graphql.client.urllib.request.urlopen",
            return_value=_fake_response({"errors": [{"message": "boom"}]}),
        ):
            with self.assertRaises(GraphQLError):
                client.execute("{ ok }")

    def test_transport_error_raises(self):
        client = GraphQLClient("https://api.example.com/graphql")
        with patch(
            "je_web_runner.utils.graphql.client.urllib.request.urlopen",
            side_effect=OSError("network down"),
        ):
            with self.assertRaises(GraphQLError):
                client.execute("{ ok }")


class TestIntrospect(unittest.TestCase):

    def test_returns_type_names(self):
        payload = {"data": {"__schema": {"types": [{"name": "User"}, {"name": "Query"}]}}}
        self.assertEqual(introspect_types(payload), ["User", "Query"])


if __name__ == "__main__":
    unittest.main()
