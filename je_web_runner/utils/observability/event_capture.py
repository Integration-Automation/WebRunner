"""
Playwright 即時事件擷取：console 訊息與網路回應，附帶斷言輔助。
Live Playwright event capture for console messages and network responses,
plus assertion helpers (``no console errors`` / ``no 5xx``).
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.webdriver.playwright_wrapper import playwright_wrapper_instance


class EventCaptureError(WebRunnerException):
    """Raised when capture cannot be attached or assertions fail."""


class EventCapture:
    """Buffer console + response events from a Playwright page."""

    def __init__(self) -> None:
        self.console_messages: List[Dict[str, Any]] = []
        self.network_responses: List[Dict[str, Any]] = []
        self._page: Optional[Any] = None
        self._handlers: Dict[str, Callable] = {}

    def attach(self, page: Any) -> None:
        """Hook ``console`` and ``response`` listeners on ``page``."""
        if self._page is not None:
            self.detach()
        self._page = page
        self._handlers = {
            "console": self._on_console,
            "response": self._on_response,
        }
        for event, handler in self._handlers.items():
            page.on(event, handler)

    def detach(self) -> None:
        """Remove listeners (best-effort)."""
        if self._page is None:
            return
        for event, handler in self._handlers.items():
            try:
                self._page.remove_listener(event, handler)
            except Exception as detach_error:  # pylint: disable=broad-except
                # Page already closed / listener already removed — log and
                # move on, the cleanup is best-effort.
                web_runner_logger.debug(
                    f"event_capture detach: ignoring {event} cleanup failure: {detach_error!r}"
                )
        self._handlers = {}
        self._page = None

    def clear(self) -> None:
        self.console_messages = []
        self.network_responses = []

    def _on_console(self, message: Any) -> None:
        try:
            location = message.location
        except Exception:  # noqa: BLE001 — older Playwright shapes
            location = None
        self.console_messages.append({
            "type": getattr(message, "type", None),
            "text": getattr(message, "text", str(message)),
            "location": location,
        })

    def _on_response(self, response: Any) -> None:
        self.network_responses.append({
            "url": response.url,
            "status": response.status,
            "method": getattr(response.request, "method", None),
            "ok": response.ok,
        })

    # ----- assertions ------------------------------------------------

    def assert_no_console_errors(self) -> None:
        errors = [m for m in self.console_messages if m.get("type") == "error"]
        if errors:
            raise EventCaptureError(f"console errors detected: {errors[:3]}")

    def assert_no_5xx(self) -> None:
        bad = [r for r in self.network_responses if r.get("status", 0) >= 500]
        if bad:
            raise EventCaptureError(f"5xx responses detected: {bad[:3]}")

    def assert_no_4xx_or_5xx(self) -> None:
        bad = [r for r in self.network_responses if r.get("status", 0) >= 400]
        if bad:
            raise EventCaptureError(f"4xx/5xx responses detected: {bad[:3]}")


event_capture = EventCapture()


# ----- module-level executor bindings ---------------------------------

def start_event_capture() -> None:
    """Attach the singleton EventCapture to the active Playwright page."""
    web_runner_logger.info("start_event_capture")
    event_capture.attach(playwright_wrapper_instance.page)


def stop_event_capture() -> None:
    web_runner_logger.info("stop_event_capture")
    event_capture.detach()


def get_console_messages() -> List[Dict[str, Any]]:
    return list(event_capture.console_messages)


def get_network_responses() -> List[Dict[str, Any]]:
    return list(event_capture.network_responses)


def clear_event_capture() -> None:
    event_capture.clear()


def assert_no_console_errors() -> None:
    event_capture.assert_no_console_errors()


def assert_no_5xx() -> None:
    event_capture.assert_no_5xx()


def assert_no_4xx_or_5xx() -> None:
    event_capture.assert_no_4xx_or_5xx()
