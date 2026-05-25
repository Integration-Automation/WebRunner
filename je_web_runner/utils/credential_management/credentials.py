"""
Credential Management API mock.

Distinct from WebAuthn (covered in [[webauthn_mock]]), the Credential
Management API exposes:

* ``PasswordCredential`` (legacy username/password autofill).
* ``FederatedCredential`` (Sign-in with Google/Facebook).
* ``navigator.credentials.preventSilentAccess``.

This module installs a shim that:

* Returns seeded credentials from ``get``.
* Records every ``store`` call so the test can assert "did the page
  remember the password?".
* Records ``preventSilentAccess`` calls so tests can verify logout
  hygiene.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException


class CredentialManagementError(WebRunnerException):
    """Raised on malformed input or assertion failure."""


INSTALL_SCRIPT = r"""
(function (seed) {
  if (window.__wr_cm__) return;
  const store = [];                  // store() calls
  const gets = [];                   // get() calls
  let preventCount = 0;
  const seeded = (seed && seed.credentials) || [];
  const cmApi = {
    get: async function (opts) {
      gets.push(opts);
      if (!seeded.length) return null;
      const c = seeded[0];
      return {
        id: c.id, type: c.type || 'password',
        name: c.name, iconURL: c.iconURL,
        password: c.password, provider: c.provider,
      };
    },
    store: async function (cred) {
      store.push({
        id: cred.id, type: cred.type || 'password',
        password: cred.password || '', provider: cred.provider || '',
      });
      return cred;
    },
    preventSilentAccess: async function () { preventCount++; },
    create: async function (opts) {
      return {id: opts.password ? opts.password.id : 'mock',
              type: opts.password ? 'password' : 'federated',
              ...(opts.password || {}),
              ...(opts.federated || {})};
    },
  };
  navigator.credentials = Object.assign(navigator.credentials || {}, cmApi);
  window.__wr_cm__ = {
    drainStored: function () { return store.splice(0); },
    drainGets: function () { return gets.splice(0); },
    preventCount: function () { return preventCount; },
  };
})(arguments[0]);
"""


@dataclass
class SeedCredential:
    id: str
    type: str = "password"        # "password" | "federated"
    name: str = ""
    password: str = ""
    provider: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def build_seed(credentials: List[SeedCredential]) -> Dict[str, Any]:
    if not isinstance(credentials, list):
        raise CredentialManagementError("credentials must be a list")
    for c in credentials:
        if not isinstance(c, SeedCredential) or not c.id:
            raise CredentialManagementError(
                "every entry must be SeedCredential with non-empty id"
            )
    return {"credentials": [c.to_dict() for c in credentials]}


@dataclass
class StoredCall:
    id: str = ""
    type: str = ""
    password: str = ""
    provider: str = ""


@dataclass
class CmLog:
    stored: List[StoredCall] = field(default_factory=list)
    gets: List[Dict[str, Any]] = field(default_factory=list)
    prevent_count: int = 0


def parse_log(payload: Any) -> CmLog:
    if not isinstance(payload, dict):
        raise CredentialManagementError("payload must be a dict")
    stored_raw = payload.get("stored") or []
    if not isinstance(stored_raw, list):
        raise CredentialManagementError("stored must be a list")
    stored = []
    for raw in stored_raw:
        if not isinstance(raw, dict):
            continue
        stored.append(StoredCall(
            id=str(raw.get("id") or ""),
            type=str(raw.get("type") or "password"),
            password=str(raw.get("password") or ""),
            provider=str(raw.get("provider") or ""),
        ))
    return CmLog(
        stored=stored,
        gets=list(payload.get("gets") or []),
        prevent_count=int(payload.get("preventCount") or 0),
    )


def assert_stored(log: CmLog, *, id: str) -> StoredCall:
    if not id:
        raise CredentialManagementError("id must be non-empty")
    for s in log.stored:
        if s.id == id:
            return s
    raise CredentialManagementError(
        f"page never called credentials.store for id={id!r}"
    )


def assert_no_password_in_clear(log: CmLog) -> None:
    """Belt-and-braces: ensure no plaintext password was *also* logged."""
    leaked = [s for s in log.stored if s.password and len(s.password) > 0]
    if leaked:
        raise CredentialManagementError(
            f"{len(leaked)} stored credential(s) leaked plaintext password "
            "into the test harness — page should not expose .password back"
        )


def assert_prevent_silent_access_called(log: CmLog, *, at_least: int = 1) -> None:
    if at_least < 1:
        raise CredentialManagementError("at_least must be >= 1")
    if log.prevent_count < at_least:
        raise CredentialManagementError(
            f"preventSilentAccess called {log.prevent_count} times, "
            f"expected >= {at_least} (logout did not clear silent sign-in)"
        )


def assert_get_requested_mediation(
    log: CmLog, *, mediation: str = "required",
) -> None:
    if mediation not in ("silent", "optional", "required", "conditional"):
        raise CredentialManagementError(f"unknown mediation {mediation!r}")
    for opts in log.gets:
        if not isinstance(opts, dict):
            continue
        if opts.get("mediation") != mediation:
            raise CredentialManagementError(
                f"credentials.get used mediation={opts.get('mediation')!r}, "
                f"expected {mediation!r}"
            )
