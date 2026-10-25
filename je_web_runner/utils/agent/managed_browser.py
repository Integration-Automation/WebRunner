"""Host-only owned Chromium sessions with a frozen network ceiling and closed actions."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Callable, Iterator, NoReturn, cast

from je_web_runner.utils.agent._managed_guard import ContextGuard, ManagedBrowserError
from je_web_runner.utils.agent._managed_owner import ManagedPlaywrightOwner
from je_web_runner.utils.agent.browser import BrowserSession
from je_web_runner.utils.agent.network_policy import BrowserOriginPolicy
from je_web_runner.utils.agent.managed_readonly import ManagedReadOnlySession
from je_web_runner.utils.agent.scoped_proxy import ScopedBrowserProxy
from je_web_runner.utils.agent.types import AgentAction, positive
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.utils.agent._browser_download import BrowserDownload, download_response
from je_web_runner.utils.agent._browser_upload import upload_bytes

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

_READ_LINK = """element => {
  if (!['A','AREA'].includes(element.tagName) || element.closest('[data-secret]')) return null;
  const value = element.href;
  return typeof value === 'string' && value.length <= 4096 ? value : null;
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

    Only installed Playwright/Chromium are used. Explicit bounded transfers accept
    no filesystem paths. There is no CDP attachment, persistent profile, caller
    script, executable path or launch-argument interface.
    This is an HTTP(S) automation boundary, not an operating-system sandbox.
    """

    contract_version = 1
    transfer_contract_version = 1
    readonly_contract_version = 1

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

    @property
    def context_id(self) -> str:
        """Return this owner's opaque context identity, without claiming current readiness."""
        return self._guard.state.context_id

    def _require_live(self) -> BrowserSession:
        if self._retired or self._session is None:
            raise ManagedBrowserError("retired")
        self._guard.require()
        return self._session

    def _require_writable(self) -> None:
        self._require_live()
        if self._guard.state.mode != "writable":
            raise ManagedBrowserError("readonly")

    def _readonly_source(self) -> tuple[BrowserSession, Any, str]:
        session = self._require_live()
        page = self._guard.page
        try:
            current = session.url
            self.policy.require(current)
        except Exception as error:
            web_runner_logger.debug("managed readonly source refused: %s", type(error).__name__)
            raise ManagedBrowserError("readonly_context_unavailable") from None
        if page is None or session.driver is not page:
            raise ManagedBrowserError("readonly_context_unavailable")
        return session, page, current

    def freeze_readonly(self) -> ManagedReadOnlySession:
        """Retire input/network permanently, retaining only the exact original context's reads."""
        self._require_live()
        state = self._guard.state
        if state.active:
            raise ManagedBrowserError("operation_active")
        if state.mode == "readonly":
            self._readonly_context(state.context_id)
            return cast(ManagedReadOnlySession, state.view)
        if state.mode != "writable":
            raise ManagedBrowserError("readonly_retirement_unconfirmed", True)
        anchor = self._readonly_source()
        state.mode = "freezing"
        try:
            self._proxy.close()
            if not self._proxy.closed:
                raise ManagedBrowserError("readonly_retirement_unconfirmed", True)
            self._guard.require()
            current = self._readonly_source()
            if current[0] is not anchor[0] or current[1] is not anchor[1] or current[2] != anchor[2]:
                raise ManagedBrowserError("readonly_context_changed")
        except Exception as error:
            self._retired = self._cleanup_failed = True
            web_runner_logger.debug("managed readonly retirement failed: %s", type(error).__name__)
            raise ManagedBrowserError("readonly_retirement_unconfirmed", True) from None
        state.anchor, state.mode = anchor, "readonly"
        identity = state.context_id
        state.view = ManagedReadOnlySession(
            self.policy, identity, lambda operation, values: self._readonly_call(identity, operation, values))
        return cast(ManagedReadOnlySession, state.view)

    def _invalidate_readonly(self) -> NoReturn:
        self._retired = True
        self._guard.fault = self._guard.fault or "readonly_context_changed"
        raise ManagedBrowserError("readonly_context_changed") from None

    def _readonly_context(self, identity: str) -> str:
        session = self._require_live()
        state, anchor = self._guard.state, self._guard.state.anchor
        if state.mode != "readonly" or identity != state.context_id or anchor is None:
            self._invalidate_readonly()
        if (session is not anchor[0] or self._guard.page is not anchor[1]
                or session.driver is not anchor[1] or not self._proxy.closed):
            self._invalidate_readonly()
        try:
            current = self._readonly_source()[2]
        except ManagedBrowserError:
            self._invalidate_readonly()
        if current != anchor[2]:
            self._invalidate_readonly()
        return current

    def _readonly_call(self, identity: str, operation: str, values: tuple[Any, ...]) -> Any:
        if operation == "close":
            if identity != self.context_id:
                raise ManagedBrowserError("readonly_context_unavailable")
            return self.close()
        before = self._readonly_context(identity)
        if operation == "capabilities":
            result = {"contract": 1, "input_supported": False,
                      "network_retired": True, "context_id": identity}
        else:
            readers: dict[str, Callable[..., Any]] = {
                "observe": self.observe, "text": self.text, "read_value": self.read_value,
                "visible": self.visible, "link": self.link, "url": lambda: self.url,
                "set_timeout": self._set_timeout}
            if operation not in readers:
                raise ManagedBrowserError("readonly_operation_refused")
            result = readers[operation](*values)
        if self._readonly_context(identity) != before:
            self._invalidate_readonly()
        return result

    @contextmanager
    def _operation(self, uncertain: bool = False) -> Iterator[BrowserSession]:
        session = self._require_live()
        self._guard.state.active += 1
        try:
            yield session
            self._guard.require(uncertain)
        except ManagedBrowserError as error:
            if uncertain:
                error.uncertain = True
            raise
        except Exception as error:
            web_runner_logger.debug("managed browser operation failed: %s", type(error).__name__)
            self._guard.fail("operation_failed")
            raise ManagedBrowserError("operation_failed", uncertain) from None
        finally:
            self._guard.state.active -= 1

    def set_timeout(self, timeout: float) -> None:
        """Set a finite positive action timeout without extending the host task deadline."""
        self._require_writable()
        self._set_timeout(timeout)

    def _set_timeout(self, timeout: float) -> None:
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
        self._require_writable()
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

    def link(self, selector: str, frame: str = "") -> str:
        """Read one complete HTTP(S) link only within this immutable origin grant."""
        result = self._read(selector, frame, _READ_LINK, "link_readback_refused")
        self.policy.require(result)
        return result

    @contextmanager
    def open_download(self, url: str) -> Iterator[BrowserDownload]:
        """Read an approved URL with URL-scoped browser cookies; the caller owns rooted file publication."""
        self._require_writable()
        self.policy.require(url)
        with self._operation(uncertain=True) as session:
            self.policy.require(session.url)

            def cookies(target: str) -> list[dict]:
                return self._owner.context.cookies([target])

            with download_response(self._proxy, url, cookies, session.timeout) as response:
                yield response

    def upload(self, selector: str, contents: bytes, name: str, frame: str = "") -> dict[str, Any]:
        """Set explicit bounded bytes on one owned file input and independently check its metadata."""
        self._require_writable()
        with self._operation(uncertain=True) as session:
            self.policy.require(session.url)
            return upload_bytes(session, selector, contents, name, frame)

    def _read(self, selector: str, frame: str, script: str, reason: str) -> str:
        with self._operation() as session:
            with session.scope(frame) as scope:
                element = session._find(scope, selector, enabled=False)  # pylint: disable=protected-access
                return _readback(element.evaluate(script), reason)

    def close(self) -> None:
        """Retire network first, then only this browser; a failed cleanup stays unconfirmed."""
        self._guard.require_thread()
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
