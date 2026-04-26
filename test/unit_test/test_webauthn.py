import unittest
from unittest.mock import MagicMock

from je_web_runner.utils.webauthn import (
    VirtualAuthenticator,
    WebAuthnError,
    enable_virtual_authenticator,
    remove_virtual_authenticator,
)
from je_web_runner.utils.webauthn.virtual_authenticator import (
    add_credential,
    clear_credentials,
    list_credentials,
    set_user_verified,
)


class TestEnable(unittest.TestCase):

    def test_enable_returns_authenticator(self):
        driver = MagicMock()

        def fake_cdp(method, params):
            if method == "WebAuthn.addVirtualAuthenticator":
                return {"authenticatorId": "auth-1"}
            return {}

        driver.execute_cdp_cmd.side_effect = fake_cdp
        auth = enable_virtual_authenticator(driver)
        self.assertEqual(auth.authenticator_id, "auth-1")

    def test_enable_without_cdp_raises(self):
        with self.assertRaises(WebAuthnError):
            enable_virtual_authenticator(object())

    def test_missing_id_raises(self):
        driver = MagicMock()
        driver.execute_cdp_cmd.return_value = {}
        with self.assertRaises(WebAuthnError):
            enable_virtual_authenticator(driver)


class TestCredentialOps(unittest.TestCase):

    def test_list_credentials(self):
        driver = MagicMock()
        driver.execute_cdp_cmd.return_value = {"credentials": [{"id": "c1"}]}
        auth = VirtualAuthenticator(authenticator_id="auth-1")
        self.assertEqual(list_credentials(driver, auth), [{"id": "c1"}])

    def test_unexpected_credentials_payload(self):
        driver = MagicMock()
        driver.execute_cdp_cmd.return_value = {"credentials": "not-a-list"}
        auth = VirtualAuthenticator(authenticator_id="auth-1")
        with self.assertRaises(WebAuthnError):
            list_credentials(driver, auth)

    def test_add_clear_remove_dispatch(self):
        driver = MagicMock()
        driver.execute_cdp_cmd.return_value = {}
        auth = VirtualAuthenticator(authenticator_id="auth-1")
        add_credential(driver, auth, {"credentialId": "x"})
        clear_credentials(driver, auth)
        set_user_verified(driver, auth, True)
        remove_virtual_authenticator(driver, auth)
        methods = [c.args[0] for c in driver.execute_cdp_cmd.call_args_list]
        self.assertEqual(methods, [
            "WebAuthn.addCredential",
            "WebAuthn.clearCredentials",
            "WebAuthn.setUserVerified",
            "WebAuthn.removeVirtualAuthenticator",
        ])


if __name__ == "__main__":
    unittest.main()
