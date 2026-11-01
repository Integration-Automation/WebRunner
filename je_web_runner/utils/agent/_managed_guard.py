"""Install managed-context restrictions before the first page exists."""
from __future__ import annotations

import threading
from typing import Any, Callable

from je_web_runner.utils.agent.network_policy import BrowserOriginPolicy
from je_web_runner.utils.agent._managed_lifecycle import ManagedContextState
from je_web_runner.utils.agent.types import AgentError
from je_web_runner.utils.logging.loggin_instance import web_runner_logger

# Defense in depth for unsupported page transports; the HTTP(S) proxy is the origin fence.
_RESTRICT_TRANSPORTS = """(() => {
  for (const name of ['RTCPeerConnection', 'webkitRTCPeerConnection', 'WebTransport',
                       'Worker', 'SharedWorker', 'WebSocket']) {
    Object.defineProperty(globalThis, name, {configurable: false, writable: false,
      value: class { constructor() { throw new Error('Transport unavailable in managed session'); } }});
  }
})()"""


class ManagedBrowserError(AgentError):
    """A bounded reason and uncertainty flag, without raw browser errors or entered data."""

    def __init__(self, reason: str, uncertain: bool = False) -> None:
        super().__init__("managed browser: " + reason)
        self.reason = reason
        self.uncertain = uncertain


class ContextGuard:
    """One page, closed HTTP(S) origins, and sticky retirement on unexpected UI."""

    def __init__(self, policy: BrowserOriginPolicy, retire_network: Callable[[], None]) -> None:
        self.policy = policy
        self._retire_network = retire_network
        self.page: Any = None
        self.fault = ""
        self.state = ManagedContextState()

    def install(self, context: Any) -> None:
        """Install before new_page; no caller-supplied scripts, routes or handlers."""
        if not callable(getattr(context, "route_web_socket", None)):
            raise ManagedBrowserError("websocket_routing_unavailable")
        context.route("**/*", self.route)
        context.route_web_socket("**/*", self.websocket)
        context.add_init_script(_RESTRICT_TRANSPORTS)
        context.on("page", self.opened_page)

    def require(self, uncertain: bool = False) -> None:
        """Reject every later command after a sticky guard fault."""
        self.require_thread()
        if self.fault:
            raise ManagedBrowserError(self.fault, uncertain)

    def require_thread(self) -> None:
        """Refuse foreign threads before entering the synchronous SDK or owned cleanup."""
        if threading.current_thread() is not self.state.owner_thread:
            raise ManagedBrowserError("wrong_thread")

    def fail(self, reason: str) -> None:
        """Cut the owned network transport before returning to an event or operation."""
        if not self.fault:
            self.fault = reason
            self._retire_network()

    def route(self, route: Any) -> None:
        """Supplement the proxy with page ownership and explicit protocol checks."""
        request = route.request
        if self.state.mode != "writable" or self.fault or not self.policy.allows(request.url):
            route.abort("blockedbyclient")
            return
        try:
            owned = self.page is not None and request.frame.page is self.page
        except Exception as error:  # pylint: disable=broad-exception-caught
            # SDK request.frame can fail for unowned worker requests; deny rather than assume ownership.
            web_runner_logger.debug("managed request ownership unavailable: %s", type(error).__name__)
            owned = False
        if not owned:
            route.abort("blockedbyclient")
            return
        route.continue_()

    @staticmethod
    def websocket(route: Any) -> None:
        """Refuse WebSockets without ever connecting to their server."""
        route.close(code=1008, reason="Unavailable in managed session")

    def opened_page(self, page: Any) -> None:
        """Keep one owned page and retire unexpected popups before subsequent actions."""
        if self.page is not None or self.fault:
            self.fail("popup_blocked")
            page.close(run_before_unload=False)
            return
        self.page = page
        page.on("dialog", self.dialog)
        page.on("download", self.download)
        page.on("filechooser", self.filechooser)
        page.on("framenavigated", self.navigated)
        page.on("crash", lambda _page: self.fail("page_crashed"))
        page.on("close", lambda _page: self.fail("page_closed"))

    def navigated(self, _frame: Any) -> None:
        """A document change after retirement cannot retain the old context's evidence authority."""
        if self.state.mode != "writable":
            self.fail("readonly_context_changed")

    def dialog(self, dialog: Any) -> None:
        """Dismiss, never accept, an unreviewed JavaScript dialog."""
        self.fail("human_review_required")
        dialog.dismiss()

    def download(self, download: Any) -> None:
        """Cancel ungranted downloads; no arbitrary path is supplied by the model."""
        self.fail("download_blocked")
        download.cancel()

    def filechooser(self, _chooser: Any) -> None:
        """Leave file inputs unset until a separate reviewed upload grant exists."""
        self.fail("upload_blocked")
