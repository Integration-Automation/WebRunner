"""WebAuthn virtual-authenticator helper via CDP."""
from je_web_runner.utils.webauthn.virtual_authenticator import (
    VirtualAuthenticator,
    WebAuthnError,
    enable_virtual_authenticator,
    remove_virtual_authenticator,
)

__all__ = [
    "VirtualAuthenticator",
    "WebAuthnError",
    "enable_virtual_authenticator",
    "remove_virtual_authenticator",
]
