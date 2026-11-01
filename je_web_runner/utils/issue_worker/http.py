"""Credential-safe platform HTTP with explicit rate-limit and retry boundaries."""
from __future__ import annotations

import time
from typing import Any

import requests

from je_web_runner.utils.issue_worker.types import ProviderError, api_url


class PlatformClient:
    """A host-owned API origin; mutations are never blindly retried."""

    def __init__(self, base_url: str, session: requests.Session | None = None) -> None:
        self.base_url = api_url(base_url)
        self.session = session or requests.Session()
        self.session.trust_env = False
        self.session.headers.update({"Accept": "application/json"})

    def close(self) -> None:
        """Release API connections."""
        self.session.close()

    def request(self, method: str, path: str, *, payload: Any = None,
                params: dict[str, Any] | None = None, missing_ok: bool = False) -> Any:
        """Return JSON or raise a sanitized failure. Only GET receives a bounded retry."""
        if not path.startswith("/") or path.startswith("//"):
            raise ProviderError("API path must stay within the configured origin", permanent=True)
        attempts = 2 if method == "GET" else 1
        for attempt in range(attempts):
            try:
                response = self.session.request(method, self.base_url + path, json=payload, params=params,
                                                timeout=30, allow_redirects=False)
            except requests.RequestException as error:
                if attempt + 1 < attempts:
                    continue
                raise ProviderError("platform connection failed", retry_after=60) from error
            if response.status_code == 404 and missing_ok:
                return None
            self._check(response)
            if response.status_code == 204:
                return None
            try:
                return response.json()
            except ValueError as error:
                raise ProviderError("platform returned invalid JSON", retry_after=60) from error
        raise ProviderError("platform request exhausted", retry_after=60)

    @staticmethod
    def _check(response: requests.Response) -> None:
        if response.is_redirect:
            raise ProviderError("platform redirects are not allowed", permanent=True)
        if response.status_code in {401, 403} and "Retry-After" not in response.headers:
            if response.headers.get("X-RateLimit-Remaining") != "0":
                raise ProviderError("platform authentication or permission denied", permanent=True)
        exhausted = response.status_code == 403 and response.headers.get("X-RateLimit-Remaining") == "0"
        if response.status_code == 429 or exhausted:
            try:
                delay = float(response.headers.get("Retry-After", "60"))
                reset = float(response.headers.get("X-RateLimit-Reset", "0")) - time.time()
            except ValueError:
                delay, reset = 60, 0
            raise ProviderError("platform rate limit reached", retry_after=max(1, delay, reset))
        if response.status_code >= 400:
            raise ProviderError(f"platform HTTP {response.status_code}", retry_after=60,
                                permanent=response.status_code < 500)
