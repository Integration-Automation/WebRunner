"""
OAuth2 / OIDC 登入流程：client_credentials / password / refresh_token。
OAuth2 / OIDC token helpers backed by ``requests`` with an in-process
token cache so repeated runs in the same process don't re-fetch.

安全 / Security:
- 認證以參數傳入；不接受寫死、不寫進 log。
  Credentials are passed as args only; never hard-coded, never logged.
- 不關閉憑證驗證（CLAUDE.md 禁止 ``verify=False``）。
  TLS verification stays on; CLAUDE.md disallows ``verify=False``.
"""
from __future__ import annotations

import time
from typing import Any, Dict, Optional

import requests

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class OAuthError(WebRunnerException):
    """Raised when a token endpoint returns an error or a config is invalid."""


_DEFAULT_TIMEOUT = 30
_token_cache: Dict[str, Dict[str, Any]] = {}


def _check_token_url(url: str) -> str:
    if not isinstance(url, str) or not url:
        raise OAuthError("token_url must be a non-empty string")
    if not (url.startswith("http://") or url.startswith("https://")):
        raise OAuthError(f"token_url must be http(s): {url!r}")
    return url


def _post_token(token_url: str, data: Dict[str, Any], timeout: int) -> Dict[str, Any]:
    safe_url = _check_token_url(token_url)
    web_runner_logger.info(f"oauth POST {safe_url}")
    response = requests.post(safe_url, data=data, timeout=timeout)
    if response.status_code >= 400:
        raise OAuthError(
            f"token endpoint responded with {response.status_code}: {response.text[:200]}"
        )
    payload = response.json()
    if not isinstance(payload, dict) or "access_token" not in payload:
        raise OAuthError(f"token response missing access_token: {payload}")
    payload["_obtained_at"] = int(time.time())
    return payload


def client_credentials_token(
    token_url: str,
    client_id: str,
    client_secret: str,
    scope: Optional[str] = None,
    cache_key: Optional[str] = None,
    timeout: int = _DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """
    OAuth2 client-credentials 流程
    Run an OAuth2 client-credentials grant and return the token response.
    """
    cached = get_cached_token(cache_key) if cache_key else None
    if cached and not _is_expired(cached):
        return cached
    data: Dict[str, Any] = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }
    if scope:
        data["scope"] = scope
    payload = _post_token(token_url, data, timeout)
    if cache_key:
        _token_cache[cache_key] = payload
    return payload


def password_grant_token(
    token_url: str,
    client_id: str,
    client_secret: str,
    username: str,
    password: str,
    scope: Optional[str] = None,
    cache_key: Optional[str] = None,
    timeout: int = _DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """
    OAuth2 password grant（多數 IdP 已棄用，僅 legacy 系統用）
    Run an OAuth2 password (Resource Owner Password Credentials) grant.
    Most modern IdPs have deprecated this flow; prefer authorization code
    or device code unless integrating with a legacy system.
    """
    cached = get_cached_token(cache_key) if cache_key else None
    if cached and not _is_expired(cached):
        return cached
    data: Dict[str, Any] = {
        "grant_type": "password",
        "client_id": client_id,
        "client_secret": client_secret,
        "username": username,
        "password": password,
    }
    if scope:
        data["scope"] = scope
    payload = _post_token(token_url, data, timeout)
    if cache_key:
        _token_cache[cache_key] = payload
    return payload


def refresh_token_grant(
    token_url: str,
    client_id: str,
    client_secret: str,
    refresh_token: str,
    cache_key: Optional[str] = None,
    timeout: int = _DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
    }
    payload = _post_token(token_url, data, timeout)
    if cache_key:
        _token_cache[cache_key] = payload
    return payload


def get_cached_token(cache_key: str) -> Optional[Dict[str, Any]]:
    if not cache_key:
        return None
    cached = _token_cache.get(cache_key)
    if cached and _is_expired(cached):
        _token_cache.pop(cache_key, None)
        return None
    return cached


def clear_token_cache() -> None:
    _token_cache.clear()


def bearer_header(access_token: str) -> Dict[str, str]:
    """Convenience: build the Authorization header for HTTP commands."""
    return {"Authorization": f"Bearer {access_token}"}


def _is_expired(token: Dict[str, Any]) -> bool:
    expires_in = token.get("expires_in")
    obtained_at = token.get("_obtained_at", 0)
    if not isinstance(expires_in, (int, float)) or expires_in <= 0:
        return False  # treat tokens with no expiry hint as still valid
    # Refresh 30 seconds early to avoid edge-of-expiry surprises.
    return time.time() >= obtained_at + float(expires_in) - 30
