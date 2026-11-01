"""Immutable exact HTTP(S) origin grants for owned browser sessions and their network transport."""
from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import re
from typing import Any, Mapping
from urllib.parse import urlsplit

from je_web_runner.utils.agent.types import AgentError


def _hostname(value: str) -> str:
    if not value.isascii() or "%" in value or len(value) > 253:
        raise AgentError("origins require canonical ASCII or punycode hostnames")
    if ":" in value:
        return "[" + str(ipaddress.IPv6Address(value)) + "]"
    if re.fullmatch(r"[0-9.]+", value):
        return str(ipaddress.IPv4Address(value))
    if re.fullmatch(r"0x[0-9a-f]+", value, re.IGNORECASE):
        raise AgentError("ambiguous numeric host is not supported")
    if ".." in value or re.fullmatch(r"[a-z0-9](?:[a-z0-9._-]*[a-z0-9.])?", value, re.IGNORECASE) is None:
        raise AgentError("invalid origin hostname")
    return value.lower()


def _unsafe_character(value: str) -> bool:
    return value.isspace() or ord(value) < 32 or ord(value) == 127


def _bounded_url(value: str) -> None:
    if not isinstance(value, str) or not 1 <= len(value) <= 4096:
        raise AgentError("URL must be bounded text")
    if "\\" in value or any(_unsafe_character(character) for character in value):
        raise AgentError("URL contains ambiguous characters")


def http_origin(value: str) -> str:
    """Canonicalize a bounded absolute URL without credentials or browser/parser ambiguities."""
    _bounded_url(value)
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise AgentError("URL must have an absolute HTTP(S) authority")
        if parsed.username is not None or parsed.password is not None:
            raise AgentError("URL credentials are not permitted")
        host = _hostname(parsed.hostname)
        default = 443 if parsed.scheme == "https" else 80
        port = parsed.port
        if port == 0:
            raise AgentError("origin port must be positive")
        suffix = "" if port is None or port == default else ":" + str(port)
        return parsed.scheme + "://" + host + suffix
    except ValueError as error:
        raise AgentError("invalid origin authority") from error


@dataclass(frozen=True)
class BrowserOriginPolicy:
    """Exact immutable origin ceiling; constructing or checking it never opens a connection."""

    origins: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.origins, (list, tuple)) or not 1 <= len(self.origins) <= 50:
            raise AgentError("origins must contain from 1 to 50 HTTP(S) origins")
        normalized = set()
        for value in self.origins:
            origin = http_origin(value)
            parsed = urlsplit(value)
            if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
                raise AgentError("origin grants cannot contain a path, query or fragment")
            normalized.add(origin)
        object.__setattr__(self, "origins", tuple(sorted(normalized)))

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> BrowserOriginPolicy:
        """Reject executable settings and unknown policy fields before opening any browser."""
        if not isinstance(value, Mapping) or set(value) != {"origins"}:
            raise AgentError("browser origin policy requires only origins")
        return cls(value["origins"])

    def allows(self, value: str) -> bool:
        """Check an absolute URL without exposing path/query data in a refusal."""
        try:
            return http_origin(value) in self.origins
        except AgentError:
            return False

    def require(self, value: str) -> str:
        """Return its canonical origin or reject a request outside this policy."""
        origin = http_origin(value)
        if origin not in self.origins:
            raise AgentError("browser request is outside allowed origins")
        return origin

    def to_dict(self) -> dict[str, Any]:
        """Return detached host configuration without connection state or credentials."""
        return {"origins": list(self.origins)}
