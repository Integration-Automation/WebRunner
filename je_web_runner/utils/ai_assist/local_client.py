"""Shared local-only Ollama transport for browser and issue coding planners."""
from __future__ import annotations

import time
import json
from typing import Any, Callable, TypeVar
from urllib.parse import urlsplit

import requests

from je_web_runner.utils.ai_assist.llm_assist import LLMAssistError
from je_web_runner.utils.exception.exceptions import WebRunnerException

_Result = TypeVar("_Result")


class LocalOllamaClient:
    """Require local weights and cloud-disabled mode, with no download or paid fallback."""

    def __init__(self, model: str, base_url: str = "http://127.0.0.1:11434",
                 error_type: type[WebRunnerException] = LLMAssistError) -> None:
        self.error_type = error_type
        target = urlsplit(base_url)
        if target.scheme != "http" or target.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise self.error_type("Ollama must use a loopback HTTP endpoint")
        if target.username or target.password or target.query or target.fragment or target.path not in {"", "/"}:
            raise self.error_type("invalid local Ollama endpoint")
        if not isinstance(model, str) or not model.strip():
            raise self.error_type("an explicitly installed local model is required")
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.trust_env = False

    def close(self) -> None:
        """Release local connections."""
        self.session.close()

    def _request(self, path: str, timeout: float, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            response = self.session.request(
                "GET" if payload is None else "POST", self.base_url + path,
                json=payload, timeout=timeout, allow_redirects=False,
            )
            response.raise_for_status()
            if response.is_redirect:
                raise self.error_type("local Ollama redirects are not allowed")
            result = response.json()
            if not isinstance(result, dict):
                raise self.error_type("local Ollama returned a non-object response")
            return result
        except (requests.RequestException, ValueError) as error:
            raise self.error_type("local Ollama request failed; check the local service and installed model") from error

    def preflight(self, timeout: float) -> None:
        """Check status and installed weights without pulling or authenticating models."""
        deadline = time.monotonic() + timeout
        status = self._request("/api/status", timeout)
        if status.get("cloud", {}).get("disabled") is not True:
            raise self.error_type("disable Ollama cloud features with OLLAMA_NO_CLOUD=1 and restart Ollama")
        tags = self._request("/api/tags", max(0.001, deadline - time.monotonic()))
        installed = {item.get("name") for item in tags.get("models", []) if not item.get("remote_model")}
        if self.model not in installed and self.model + ":latest" not in installed:
            raise self.error_type("requested local model is not installed; install an open-source local model first")

    def structured(self, instructions: str, context: dict[str, Any], schema: dict[str, Any],
                   parse: Callable[[Any], _Result], timeout: float, label: str = "response") -> _Result:
        """Decode one schema-constrained reply with one bounded correction, never echoing raw output."""
        deadline = time.monotonic() + timeout
        messages = [{"role": "system", "content": instructions},
                    {"role": "user", "content": json.dumps(context, ensure_ascii=False)}]
        for attempt in range(2):
            result = self._request("/api/chat", max(0.001, deadline - time.monotonic()), {
                "model": self.model, "messages": messages, "format": schema,
                "stream": False, "options": {"temperature": 0},
            })
            try:
                return parse(json.loads(result["message"]["content"]))
            except (ValueError, KeyError, TypeError, WebRunnerException) as error:
                if attempt:
                    raise self.error_type(f"local model returned invalid {label} twice") from error
                messages.append({"role": "user", "content": "Invalid response. Return one valid object."})
        raise self.error_type("local model did not return a structured response")
