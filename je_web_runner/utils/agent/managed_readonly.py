"""Closed host-created reads from an already frozen original managed browser context."""
from __future__ import annotations

from typing import Any, Callable, cast

from je_web_runner.utils.agent.network_policy import BrowserOriginPolicy


class ManagedReadOnlySession:
    """A view issued by freeze_readonly; it never accepts a page, action, script or transport."""

    contract_version = 1

    def __init__(self, policy: BrowserOriginPolicy, context_id: str,
                 invoke: Callable[[str, tuple[Any, ...]], Any]) -> None:
        self._policy, self._context_id, self._invoke = policy, context_id, invoke

    @property
    def policy(self) -> BrowserOriginPolicy:
        """Return the original immutable grant; metadata alone is not current authority."""
        return self._policy

    @property
    def context_id(self) -> str:
        """Return a stable historical identity, not a replacement for live capability checks."""
        return self._context_id

    def capabilities(self) -> dict[str, Any]:
        """Confirm the still-live exact context and its completed transport retirement."""
        return cast(dict[str, Any], self._invoke("capabilities", ()))

    @property
    def url(self) -> str:
        """Read the owned page's current reviewed-origin URL."""
        return cast(str, self._invoke("url", ()))

    def observe(self, step: int = 0) -> dict[str, Any]:
        """Read a fresh in-memory semantic observation without screenshots or form values."""
        return cast(dict[str, Any], self._invoke("observe", (step,)))

    def text(self, selector: str = "body", frame: str = "") -> str:
        """Read complete bounded visible text through the existing secret-aware fixed script."""
        return cast(str, self._invoke("text", (selector, frame)))

    def read_value(self, selector: str, frame: str = "") -> str:
        """Read a bounded nonsecret field; unsupported or partial values remain refused."""
        return cast(str, self._invoke("read_value", (selector, frame)))

    def visible(self, selector: str, frame: str = "") -> bool:
        """Check a unique visible element, preserving ambiguity as a refusal."""
        return cast(bool, self._invoke("visible", (selector, frame)))

    def link(self, selector: str, frame: str = "") -> str:
        """Read a complete link which remains within the original immutable origin grant."""
        return cast(str, self._invoke("link", (selector, frame)))

    def set_timeout(self, timeout: float) -> None:
        """Bound read calls without creating input authority or extending any host deadline."""
        self._invoke("set_timeout", (timeout,))

    def close(self) -> None:
        """Close only this view's original owner, including on repeated close."""
        self._invoke("close", ())

    def __enter__(self) -> ManagedReadOnlySession:
        self.capabilities()
        return self

    def __exit__(self, *_error: object) -> None:
        self.close()
