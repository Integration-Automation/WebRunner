import unittest
from unittest.mock import MagicMock, patch

from je_web_runner.utils.auth.oauth import (
    OAuthError,
    bearer_header,
    clear_token_cache,
    client_credentials_token,
    password_grant_token,
    refresh_token_grant,
)


def _success_response(**overrides):
    response = MagicMock(status_code=200, text="ok")
    payload = {
        "access_token": "abc",
        "token_type": "Bearer",
        "expires_in": 3600,
    }
    payload.update(overrides)
    response.json.return_value = payload
    return response


class TestClientCredentials(unittest.TestCase):

    def setUp(self):
        clear_token_cache()

    def test_invalid_url_raises(self):
        with self.assertRaises(OAuthError):
            client_credentials_token("ftp://example.com", "id", "secret")

    def test_returns_token_response(self):
        with patch("je_web_runner.utils.auth.oauth.requests.post",
                   return_value=_success_response()) as post_mock:
            result = client_credentials_token(
                "https://idp.example/oauth2/token", "id", "secret", scope="read",
            )
            self.assertEqual(result["access_token"], "abc")
            data = post_mock.call_args.kwargs["data"]
            self.assertEqual(data["grant_type"], "client_credentials")
            self.assertEqual(data["scope"], "read")

    def test_cache_returns_same_token_within_ttl(self):
        with patch("je_web_runner.utils.auth.oauth.requests.post",
                   return_value=_success_response()) as post_mock:
            token1 = client_credentials_token(
                "https://idp.example/oauth2/token", "id", "secret", cache_key="svc",
            )
            token2 = client_credentials_token(
                "https://idp.example/oauth2/token", "id", "secret", cache_key="svc",
            )
            self.assertIs(token1, token2)
            self.assertEqual(post_mock.call_count, 1)

    def test_error_status_raises(self):
        response = MagicMock(status_code=401, text="bad credentials")
        with patch("je_web_runner.utils.auth.oauth.requests.post", return_value=response):
            with self.assertRaises(OAuthError):
                client_credentials_token("https://idp.example/oauth2/token", "id", "secret")


class TestPasswordGrant(unittest.TestCase):

    def test_password_grant_dispatches(self):
        with patch("je_web_runner.utils.auth.oauth.requests.post",
                   return_value=_success_response()) as post_mock:
            password_grant_token(  # nosec B106 — fake fixture, mocked transport
                "https://idp.example/oauth2/token", "id", "secret",
                username="alice", password="hunter2",
            )
            data = post_mock.call_args.kwargs["data"]
            self.assertEqual(data["grant_type"], "password")
            self.assertEqual(data["username"], "alice")


class TestRefreshGrant(unittest.TestCase):

    def test_refresh_dispatches(self):
        with patch("je_web_runner.utils.auth.oauth.requests.post",
                   return_value=_success_response()) as post_mock:
            refresh_token_grant(
                "https://idp.example/oauth2/token", "id", "secret",
                refresh_token="rt-xyz",
            )
            data = post_mock.call_args.kwargs["data"]
            self.assertEqual(data["grant_type"], "refresh_token")
            self.assertEqual(data["refresh_token"], "rt-xyz")


class TestBearerHeader(unittest.TestCase):

    def test_format(self):
        self.assertEqual(bearer_header("abc"), {"Authorization": "Bearer abc"})


if __name__ == "__main__":
    unittest.main()
