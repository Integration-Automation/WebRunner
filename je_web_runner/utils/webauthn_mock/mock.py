"""
WebAuthn / FIDO2 / Passkey mock.

Real authenticators (Touch ID, YubiKey, Windows Hello) can't run in CI.
This module installs a deterministic ``navigator.credentials`` shim that
satisfies the WebAuthn registration & assertion ceremonies with
pre-seeded key material, so the page-under-test can complete sign-up
and sign-in flows without user hardware.

Python helpers also provide canned credentials and a verifier so backend
contract tests can confirm the server actually validates the attestation
/ assertion they get from the shim.
"""
from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass, field
from typing import Any, Dict, List

from je_web_runner.utils.exception.exceptions import WebRunnerException


class WebauthnMockError(WebRunnerException):
    """Raised on malformed credentials or assertion failures."""


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


INSTALL_SCRIPT = r"""
(function (creds) {
  if (window.__wr_webauthn__) return;
  const map = {};            // id -> credential record
  const created = [];        // every navigator.credentials.create call
  const requested = [];      // every navigator.credentials.get call
  function b64dec(s) {
    s = s.replace(/-/g, '+').replace(/_/g, '/');
    while (s.length % 4) s += '=';
    return Uint8Array.from(atob(s), c => c.charCodeAt(0)).buffer;
  }
  for (const c of creds) map[c.id] = c;
  navigator.credentials = navigator.credentials || {};
  navigator.credentials.create = async function (opts) {
    created.push(opts);
    const id = 'wr-cred-' + Object.keys(map).length;
    const record = creds[0] || {id: id, publicKeyB64: '', signCount: 0};
    return {
      id: record.id, type: 'public-key',
      rawId: b64dec(record.id),
      response: {
        clientDataJSON: b64dec(record.clientDataJSONB64 || ''),
        attestationObject: b64dec(record.attestationObjectB64 || ''),
      },
      getClientExtensionResults: () => ({}),
    };
  };
  navigator.credentials.get = async function (opts) {
    requested.push(opts);
    const allowed = (opts.publicKey && opts.publicKey.allowCredentials) || [];
    const wanted = allowed.length ? allowed[0].id : null;
    const id = wanted ? (typeof wanted === 'string' ? wanted
      : btoa(String.fromCharCode.apply(null, new Uint8Array(wanted))))
      : Object.keys(map)[0];
    const record = map[id] || creds[0];
    if (!record) throw new Error('no credential');
    return {
      id: record.id, type: 'public-key',
      rawId: b64dec(record.id),
      response: {
        clientDataJSON: b64dec(record.clientDataJSONB64 || ''),
        authenticatorData: b64dec(record.authenticatorDataB64 || ''),
        signature: b64dec(record.signatureB64 || ''),
        userHandle: record.userHandleB64 ? b64dec(record.userHandleB64) : null,
      },
      getClientExtensionResults: () => ({}),
    };
  };
  window.__wr_webauthn__ = {
    drainCreated: function () { return created.splice(0); },
    drainRequested: function () { return requested.splice(0); },
  };
})(arguments[0]);
"""


@dataclass
class MockCredential:
    """Minimal credential record the install script accepts."""

    id: str
    public_key_b64: str = ""
    sign_count: int = 0
    client_data_json_b64: str = ""
    attestation_object_b64: str = ""
    authenticator_data_b64: str = ""
    signature_b64: str = ""
    user_handle_b64: str = ""

    def to_dict(self) -> Dict[str, Any]:
        # JS shim uses camelCase keys
        return {
            "id": self.id,
            "publicKeyB64": self.public_key_b64,
            "signCount": self.sign_count,
            "clientDataJSONB64": self.client_data_json_b64,
            "attestationObjectB64": self.attestation_object_b64,
            "authenticatorDataB64": self.authenticator_data_b64,
            "signatureB64": self.signature_b64,
            "userHandleB64": self.user_handle_b64,
        }


def build_credential(
    user_handle: str, rp_id: str, *, sign_count: int = 0,
) -> MockCredential:
    """Synthesize a deterministic-but-unique credential for a test user."""
    if not user_handle or not rp_id:
        raise WebauthnMockError("user_handle and rp_id are required")
    seed = hashlib.sha256(
        f"{user_handle}|{rp_id}".encode("utf-8"),
    ).digest()
    cred_id = _b64url(seed[:16])
    public_key = _b64url(seed[16:])
    client_data = {"type": "webauthn.create", "challenge": _b64url(seed[:32]),
                   "origin": f"https://{rp_id}"}
    import json
    return MockCredential(
        id=cred_id,
        public_key_b64=public_key,
        sign_count=sign_count,
        client_data_json_b64=_b64url(
            json.dumps(client_data, separators=(",", ":")).encode("utf-8"),
        ),
        attestation_object_b64=_b64url(b"\xa0"),   # CBOR null map
        authenticator_data_b64=_b64url(seed[:37]),
        signature_b64=_b64url(secrets.token_bytes(64)),
        user_handle_b64=_b64url(user_handle.encode("utf-8")),
    )


@dataclass
class CeremonyLog:
    created: List[Dict[str, Any]] = field(default_factory=list)
    requested: List[Dict[str, Any]] = field(default_factory=list)


def parse_log(payload: Any) -> CeremonyLog:
    if not isinstance(payload, dict):
        raise WebauthnMockError("payload must be dict")
    return CeremonyLog(
        created=list(payload.get("created") or []),
        requested=list(payload.get("requested") or []),
    )


def assert_registered(log: CeremonyLog) -> None:
    if not log.created:
        raise WebauthnMockError(
            "page never called navigator.credentials.create"
        )


def assert_signed_in(log: CeremonyLog) -> None:
    if not log.requested:
        raise WebauthnMockError(
            "page never called navigator.credentials.get"
        )


def _extract_uv(opts: Any) -> Optional[str]:
    if not isinstance(opts, dict):
        return None
    pk = opts.get("publicKey")
    if not isinstance(pk, dict):
        return None
    sel = pk.get("authenticatorSelection")
    if isinstance(sel, dict) and sel.get("userVerification"):
        return sel.get("userVerification")
    return pk.get("userVerification")


def assert_user_verification(
    log: CeremonyLog, *, level: str = "required",
) -> None:
    """Both ceremonies should request the given user-verification level."""
    if level not in ("required", "preferred", "discouraged"):
        raise WebauthnMockError(f"invalid level {level!r}")
    for kind, opts_list in (("create", log.created),
                            ("get", log.requested)):
        for opts in opts_list:
            actual = _extract_uv(opts)
            if actual and actual != level:
                raise WebauthnMockError(
                    f"{kind} ceremony asked for "
                    f"userVerification={actual!r}, expected {level!r}"
                )
