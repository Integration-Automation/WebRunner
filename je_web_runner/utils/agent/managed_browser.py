"""Host-only owned Chromium sessions with a frozen network ceiling and closed actions."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from je_web_runner.utils.agent._managed_guard import ContextGuard, ManagedBrowserError
from je_web_runner.utils.agent._managed_owner import ManagedPlaywrightOwner
from je_web_runner.utils.agent.browser import BrowserSession
from je_web_runner.utils.agent.network_policy import BrowserOriginPolicy
from je_web_runner.utils.agent.scoped_proxy import ScopedBrowserProxy
from je_web_runner.utils.agent.types import AgentAction, positive
from je_web_runner.utils.logging.loggin_instance import web_runner_logger

_READ_VALUE = """element => {
  const tag = element.tagName.toLowerCase();
  const type = (element.getAttribute('type') || '').toLowerCase();
  if (!['input','textarea','select'].includes(tag) || ['password','hidden','file'].includes(type)) return null;
  if (element.closest('[data-secret]') || element.autocomplete === 'current-password'
      || element.autocomplete === 'new-password') return null;
  const value = String(element.value);
  return value.length <= 8000 ? value : null;
}"""

_READ_TEXT = """element => {
  if (element.closest('[data-secret]') || element.querySelector('[data-secret]')) return null;
  const value = element.innerText;
  return typeof value === 'string' && value.length <= 8000 ? value : null;
}"""


def _readback(value: Any, reason: str) -> str:
    if not isinstance(value, str) or len(value) > 8000:
        raise ManagedBrowserError(reason)
    try:
        if len(value.encode("utf-16-le")) > 16000:
            raise ManagedBrowserError(reason)
    except UnicodeError:
        raise ManagedBrowserError(reason) from None
    return value


class ManagedBrowserSession:
    """One host-thread owned headless browser; explicit close or context management is required.

    Only installed Playwright/Chromium are used. There is no download, CDP attachment,
    persistent profile, caller script, executable path or launch-argument interface.
    This is an HTTP(S) automation boundary, not an operating-system sandbox.
    """

    contract_version = 1

    def __init__(self, policy: BrowserOriginPolicy) -> None:
        self._proxy = ScopedBrowserProxy(policy)
        self._guard = ContextGuard(policy, self._proxy.close)
        self._owner = ManagedPlaywrightOwner(self._guard)
        self._session: BrowserSession | None = None
        self._retired = False
        self._closed = False
        self._cleanup_failed = False

    @classmethod
    def open(cls, policy: BrowserOriginPolicy) -> ManagedBrowserSession:
        """Start a fresh proxy and context before the first blank page; never auto-install."""
        instance = cls(policy)
        try:
            instance._proxy.start()
            instance._owner.launch(headless=True, proxy=instance._proxy.browser_proxy(),
                                   chromium_sandbox=True, args=["--disable-quic", "--disable-http2",
                                   "--force-webrtc-ip-handling-policy=disable_non_proxied_udp"],
                                   context_options={"accept_downloads": False, "service_workers": "block",
                                                    "permissions": [], "ignore_https_errors": False})
            instance._session = BrowserSession(instance._owner.page, "playwright")
            instance._guard.require()
            return instance
        except Exception as error:
            web_runner_logger.debug("managed browser startup failed: %s", type(error).__name__)
            instance.close()
            raise ManagedBrowserError("startup_failed") from None

    @property
    def policy(self) -> BrowserOriginPolicy:
        """The immutable reviewed origin grants, without private transport credentials."""
        return self._proxy.policy

    @property
    def closed(self) -> bool:
        """True only after normal cleanup returned successfully, never on a failed close."""
        return self._closed

    @contextmanager
    def _operation(self, uncertain: bool = False) -> Iterator[BrowserSession]:
        if self._retired or self._session is None:
            raise ManagedBrowserError("retired")
        self._guard.require()
        try:
            yield self._session
            self._guard.require(uncertain)
        except ManagedBrowserError as error:
            if uncertain:
                error.uncertain = True
            raise
        except Exception as error:
            web_runner_logger.debug("managed browser operation failed: %s", type(error).__name__)
            self._guard.fail("operation_failed")
            raise ManagedBrowserError("operation_failed", uncertain) from None

    def set_timeout(self, timeout: float) -> None:
        """Set a finite positive action timeout without extending the host task deadline."""
        positive(timeout, "timeout")
        with self._operation() as session:
            session.set_timeout(timeout)

    def observe(self, step: int = 0) -> dict[str, Any]:
        """Read semantic observations in memory; form values and screenshots are not collected."""
        if isinstance(step, bool) or not isinstance(step, int) or step < 0:
            raise ManagedBrowserError("invalid_step")
        with self._operation() as session:
            return session.observe(step)

    @property
    def url(self) -> str:
        """The owned main-page URL, subject to the same retirement checks as other reads."""
        with self._operation() as session:
            return session.url

    def perform(self, action: AgentAction) -> str | None:
        """Execute once; a failed effect is uncertain and is never retried by this SDK."""
        if not isinstance(action, AgentAction):
            raise ManagedBrowserError("invalid_action")
        if action.kind == "navigate":
            self.policy.require(action.value)
        if action.kind in {"fill", "select"}:
            _readback(action.value, "invalid_action_value")
        uncertain = action.kind in {"navigate", "click", "fill", "select", "check", "scroll"}
        with self._operation(uncertain) as session:
            return session.perform(action)

    def text(self, selector: str = "body", frame: str = "") -> str:
        """Read complete bounded visible text, refusing marked secret descendants and ancestors."""
        return self._read(selector, frame, _READ_TEXT, "text_readback_refused")

    def visible(self, selector: str, frame: str = "") -> bool:
        """Check one unique visible element, preserving ambiguity as a refusal."""
        with self._operation() as session:
            return session.visible(selector, frame)

    def read_value(self, selector: str, frame: str = "") -> str:
        """Explicit bounded form readback; password, file, hidden and secret controls are refused."""
        return self._read(selector, frame, _READ_VALUE, "value_readback_refused")

    def _read(self, selector: str, frame: str, script: str, reason: str) -> str:
        with self._operation() as session:
            with session.scope(frame) as scope:
                element = session._find(scope, selector, enabled=False)  # pylint: disable=protected-access
                return _readback(element.evaluate(script), reason)

    def close(self) -> None:
        """Retire network first, then only this browser; a failed cleanup stays unconfirmed."""
        if self._closed:
            return
        self._retired = True
        try:
            try:
                self._proxy.close()
            except Exception as error:
                web_runner_logger.debug("managed network retirement failed: %s", type(error).__name__)
                raise ManagedBrowserError("cleanup_unconfirmed") from None
        finally:
            try:
                self._owner.quit()
            except Exception as error:
                self._cleanup_failed = True
                web_runner_logger.debug("managed browser cleanup failed: %s", type(error).__name__)
                raise ManagedBrowserError("cleanup_unconfirmed") from None
        if self._cleanup_failed:
            raise ManagedBrowserError("cleanup_unconfirmed")
        self._session = None
        self._closed = True

    def __enter__(self) -> ManagedBrowserSession:
        self._guard.require()
        if self._retired or self._session is None:
            raise ManagedBrowserError("retired")
        return self

    def __exit__(self, *_error: object) -> None:
        self.close()
