"""Unit tests for je_web_runner.utils.credential_management."""
import unittest

from je_web_runner.utils.credential_management.credentials import (
    CmLog,
    CredentialManagementError,
    INSTALL_SCRIPT,
    SeedCredential,
    StoredCall,
    assert_get_requested_mediation,
    assert_no_password_in_clear,
    assert_prevent_silent_access_called,
    assert_stored,
    build_seed,
    parse_log,
)


class TestBuildSeed(unittest.TestCase):

    def test_basic(self):
        seed = build_seed([SeedCredential(id="alice", password="pw")])
        self.assertEqual(seed["credentials"][0]["id"], "alice")

    def test_bad_list(self):
        with self.assertRaises(CredentialManagementError):
            build_seed("nope")

    def test_bad_entry(self):
        with self.assertRaises(CredentialManagementError):
            build_seed([SeedCredential(id="")])


class TestScript(unittest.TestCase):

    def test_contains(self):
        self.assertIn("navigator.credentials", INSTALL_SCRIPT)
        self.assertIn("__wr_cm__", INSTALL_SCRIPT)


class TestParse(unittest.TestCase):

    def test_basic(self):
        log = parse_log({"stored": [{"id": "x", "password": "p"}],
                         "gets": [{}], "preventCount": 1})
        self.assertEqual(log.stored[0].id, "x")
        self.assertEqual(log.prevent_count, 1)

    def test_bad_payload(self):
        with self.assertRaises(CredentialManagementError):
            parse_log("nope")

    def test_bad_stored(self):
        with self.assertRaises(CredentialManagementError):
            parse_log({"stored": "nope"})

    def test_skip_non_dict_stored(self):
        log = parse_log({"stored": ["x", {"id": "ok"}]})
        self.assertEqual(len(log.stored), 1)


class TestAssertStored(unittest.TestCase):

    def test_pass(self):
        s = assert_stored(CmLog(stored=[StoredCall(id="a")]), id="a")
        self.assertEqual(s.id, "a")

    def test_fail(self):
        with self.assertRaises(CredentialManagementError):
            assert_stored(CmLog(), id="a")

    def test_empty_id(self):
        with self.assertRaises(CredentialManagementError):
            assert_stored(CmLog(), id="")


class TestNoPlaintext(unittest.TestCase):

    def test_pass(self):
        assert_no_password_in_clear(CmLog(stored=[StoredCall(id="a")]))

    def test_fail(self):
        with self.assertRaises(CredentialManagementError):
            assert_no_password_in_clear(
                CmLog(stored=[StoredCall(id="a", password="leak")]),
            )


class TestPreventSilent(unittest.TestCase):

    def test_pass(self):
        assert_prevent_silent_access_called(CmLog(prevent_count=1))

    def test_fail(self):
        with self.assertRaises(CredentialManagementError):
            assert_prevent_silent_access_called(CmLog(prevent_count=0))

    def test_bad_min(self):
        with self.assertRaises(CredentialManagementError):
            assert_prevent_silent_access_called(CmLog(), at_least=0)


class TestMediation(unittest.TestCase):

    def test_pass(self):
        assert_get_requested_mediation(
            CmLog(gets=[{"mediation": "required"}]),
            mediation="required",
        )

    def test_fail(self):
        with self.assertRaises(CredentialManagementError):
            assert_get_requested_mediation(
                CmLog(gets=[{"mediation": "silent"}]),
                mediation="required",
            )

    def test_bad_mediation(self):
        with self.assertRaises(CredentialManagementError):
            assert_get_requested_mediation(CmLog(), mediation="weird")


if __name__ == "__main__":
    unittest.main()
