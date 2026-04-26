"""
WebAuthn 虛擬驗證器：透過 CDP ``WebAuthn.addVirtualAuthenticator`` 模擬 passkey。
WebAuthn virtual authenticator helper. Wraps the CDP commands so tests can
exercise passkey / FIDO2 sign-in flows without real hardware.

Reference: https://chromedevtools.github.io/devtools-protocol/tot/WebAuthn/
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException


class WebAuthnError(WebRunnerException):
    """Raised when CDP doesn't surface the WebAuthn domain or call fails."""


@dataclass(frozen=True)
class VirtualAuthenticator:
    authenticator_id: str
    protocol: str = "ctap2"
    transport: str = "internal"
    has_resident_key: bool = True
    has_user_verification: bool = True
    is_user_verified: bool = True


def _send(driver: Any, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
    if not hasattr(driver, "execute_cdp_cmd"):
        raise WebAuthnError("driver does not expose execute_cdp_cmd (Chromium only)")
    return driver.execute_cdp_cmd(method, params) or {}


def enable_virtual_authenticator(
    driver: Any,
    protocol: str = "ctap2",
    transport: str = "internal",
    has_resident_key: bool = True,
    has_user_verification: bool = True,
    is_user_verified: bool = True,
) -> VirtualAuthenticator:
    """
    啟用 ``WebAuthn`` domain 並新增一個 virtual authenticator
    Enable the ``WebAuthn`` CDP domain and register a fresh virtual
    authenticator. Returns a :class:`VirtualAuthenticator` whose
    ``authenticator_id`` callers must pass back for credential mgmt.
    """
    _send(driver, "WebAuthn.enable", {})
    response = _send(driver, "WebAuthn.addVirtualAuthenticator", {
        "options": {
            "protocol": protocol,
            "transport": transport,
            "hasResidentKey": has_resident_key,
            "hasUserVerification": has_user_verification,
            "isUserVerified": is_user_verified,
            "automaticPresenceSimulation": True,
        },
    })
    authenticator_id = response.get("authenticatorId")
    if not isinstance(authenticator_id, str):
        raise WebAuthnError(
            f"WebAuthn.addVirtualAuthenticator returned no authenticatorId: {response!r}"
        )
    return VirtualAuthenticator(
        authenticator_id=authenticator_id,
        protocol=protocol,
        transport=transport,
        has_resident_key=has_resident_key,
        has_user_verification=has_user_verification,
        is_user_verified=is_user_verified,
    )


def list_credentials(driver: Any, authenticator: VirtualAuthenticator) -> List[Dict[str, Any]]:
    response = _send(driver, "WebAuthn.getCredentials", {
        "authenticatorId": authenticator.authenticator_id,
    })
    creds = response.get("credentials") or []
    if not isinstance(creds, list):
        raise WebAuthnError(f"unexpected credentials payload: {creds!r}")
    return creds


def add_credential(
    driver: Any,
    authenticator: VirtualAuthenticator,
    credential: Dict[str, Any],
) -> None:
    _send(driver, "WebAuthn.addCredential", {
        "authenticatorId": authenticator.authenticator_id,
        "credential": credential,
    })


def clear_credentials(driver: Any, authenticator: VirtualAuthenticator) -> None:
    _send(driver, "WebAuthn.clearCredentials", {
        "authenticatorId": authenticator.authenticator_id,
    })


def remove_virtual_authenticator(
    driver: Any,
    authenticator: VirtualAuthenticator,
) -> None:
    _send(driver, "WebAuthn.removeVirtualAuthenticator", {
        "authenticatorId": authenticator.authenticator_id,
    })


def set_user_verified(
    driver: Any,
    authenticator: VirtualAuthenticator,
    is_user_verified: bool,
) -> None:
    _send(driver, "WebAuthn.setUserVerified", {
        "authenticatorId": authenticator.authenticator_id,
        "isUserVerified": is_user_verified,
    })


def set_automatic_presence_simulation(
    driver: Any,
    authenticator: VirtualAuthenticator,
    enabled: bool,
) -> None:
    _send(driver, "WebAuthn.setAutomaticPresenceSimulation", {
        "authenticatorId": authenticator.authenticator_id,
        "enabled": enabled,
    })
