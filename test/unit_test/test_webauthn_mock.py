"""Unit tests for je_web_runner.utils.webauthn_mock."""
import unittest

from je_web_runner.utils.webauthn_mock.mock import (
    CeremonyLog,
    INSTALL_SCRIPT,
    WebauthnMockError,
    assert_registered,
    assert_signed_in,
    assert_user_verification,
    build_credential,
    parse_log,
)


class TestBuild(unittest.TestCase):

    def test_deterministic(self):
        a = build_credential("alice", "example.com")
        b = build_credential("alice", "example.com")
        self.assertEqual(a.id, b.id)

    def test_distinct_per_user(self):
        a = build_credential("alice", "example.com")
        b = build_credential("bob", "example.com")
        self.assertNotEqual(a.id, b.id)

    def test_missing_args(self):
        with self.assertRaises(WebauthnMockError):
            build_credential("", "x")
        with self.assertRaises(WebauthnMockError):
            build_credential("x", "")

    def test_to_dict_keys(self):
        d = build_credential("alice", "x.com").to_dict()
        self.assertIn("publicKeyB64", d)
        self.assertIn("signCount", d)


class TestScript(unittest.TestCase):

    def test_contains_hooks(self):
        self.assertIn("navigator.credentials", INSTALL_SCRIPT)
        self.assertIn("__wr_webauthn__", INSTALL_SCRIPT)


class TestParse(unittest.TestCase):

    def test_basic(self):
        log = parse_log({"created": [{"x": 1}], "requested": []})
        self.assertEqual(len(log.created), 1)

    def test_bad(self):
        with self.assertRaises(WebauthnMockError):
            parse_log("nope")


class TestAssertRegistered(unittest.TestCase):

    def test_pass(self):
        assert_registered(CeremonyLog(created=[{"x": 1}]))

    def test_fail(self):
        with self.assertRaises(WebauthnMockError):
            assert_registered(CeremonyLog())


class TestAssertSignedIn(unittest.TestCase):

    def test_pass(self):
        assert_signed_in(CeremonyLog(requested=[{"x": 1}]))

    def test_fail(self):
        with self.assertRaises(WebauthnMockError):
            assert_signed_in(CeremonyLog())


class TestUserVerification(unittest.TestCase):

    def test_pass(self):
        log = CeremonyLog(created=[{
            "publicKey": {
                "authenticatorSelection": {"userVerification": "required"},
            },
        }])
        assert_user_verification(log, level="required")

    def test_fail(self):
        log = CeremonyLog(created=[{
            "publicKey": {
                "authenticatorSelection": {"userVerification": "discouraged"},
            },
        }])
        with self.assertRaises(WebauthnMockError):
            assert_user_verification(log, level="required")

    def test_bad_level(self):
        with self.assertRaises(WebauthnMockError):
            assert_user_verification(CeremonyLog(), level="weird")

    def test_empty_log_pass(self):
        assert_user_verification(CeremonyLog(), level="required")


if __name__ == "__main__":
    unittest.main()
