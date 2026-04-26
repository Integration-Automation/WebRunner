"""
WebDriver BiDi 統一橋：Selenium / Playwright 兩個後端共用的 event 訂閱介面。
Unified BiDi-style event bridge over Selenium 4's BiDi or Playwright's
context/page event API. Callers ``subscribe`` to a logical event name and
get a :class:`BidiSubscription` they can ``unsubscribe()`` later.

The abstraction hides:

- Selenium 4's ``driver.script.add_console_message_handler`` / ``driver.bidi_connection``.
- Playwright's ``page.on("console", fn)`` / ``page.on("response", fn)`` / context-level events.

Logical event names supported by default: ``console``, ``response``,
``request``, ``page_load``. Additional names can be registered via
:meth:`BidiBridge.register_translator`.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class BidiBackendError(WebRunnerException):
    """Raised when subscription / unsubscription fails or backend is unsupported."""


@dataclass
class BidiEvent:
    """Backend-agnostic event payload."""

    name: str
    payload: Dict[str, Any]


@dataclass
class BidiSubscription:
    """Handle returned by :meth:`BidiBridge.subscribe`."""

    subscription_id: int
    event: str
    backend: str
    detach: Callable[[], None]

    def unsubscribe(self) -> None:
        try:
            self.detach()
        except Exception as error:  # pylint: disable=broad-except
            web_runner_logger.warning(
                f"bidi unsubscribe {self.event!r} failed: {error!r}"
            )


# Translator signature: (target, callback) -> detach_fn
Translator = Callable[[Any, Callable[[BidiEvent], None]], Callable[[], None]]


def _selenium_console_translator(target: Any,
                                  callback: Callable[[BidiEvent], None]) -> Callable[[], None]:
    if not hasattr(target, "script") or not hasattr(target.script, "add_console_message_handler"):
        raise BidiBackendError("driver.script.add_console_message_handler missing")

    def adapter(message: Any) -> None:
        callback(BidiEvent(name="console", payload={
            "type": getattr(message, "type", None),
            "text": getattr(message, "text", None),
        }))

    handle = target.script.add_console_message_handler(adapter)

    def detach() -> None:
        if hasattr(target.script, "remove_console_message_handler"):
            target.script.remove_console_message_handler(handle)

    return detach


def _playwright_event_translator(event_name: str) -> Translator:

    def translator(target: Any, callback: Callable[[BidiEvent], None]) -> Callable[[], None]:
        if not hasattr(target, "on") or not hasattr(target, "remove_listener"):
            raise BidiBackendError("page does not expose on/remove_listener")

        def adapter(payload: Any) -> None:
            callback(BidiEvent(
                name=event_name,
                payload=_extract_playwright_payload(event_name, payload),
            ))

        target.on(event_name, adapter)

        def detach() -> None:
            try:
                target.remove_listener(event_name, adapter)
            except Exception as error:  # pylint: disable=broad-except
                web_runner_logger.debug(
                    f"playwright remove_listener {event_name!r} failed: {error!r}"
                )

        return detach

    return translator


def _extract_playwright_payload(event_name: str, payload: Any) -> Dict[str, Any]:
    if event_name == "console":
        return {
            "type": getattr(payload, "type", None),
            "text": getattr(payload, "text", None),
        }
    if event_name == "response":
        return {
            "url": getattr(payload, "url", None),
            "status": getattr(payload, "status", None),
        }
    if event_name == "request":
        return {
            "url": getattr(payload, "url", None),
            "method": getattr(payload, "method", None),
        }
    if event_name == "page_load":
        return {"url": getattr(payload, "url", None)}
    return {"raw": str(payload)[:200]}


class BidiBridge:
    """Backend-detecting bridge for BiDi-style event subscription."""

    def __init__(self) -> None:
        self._subscriptions: Dict[int, BidiSubscription] = {}
        self._counter = itertools.count(1)
        self._translators: Dict[str, Dict[str, Translator]] = {
            "selenium": {"console": _selenium_console_translator},
            "playwright": {
                "console": _playwright_event_translator("console"),
                "response": _playwright_event_translator("response"),
                "request": _playwright_event_translator("request"),
                "page_load": _playwright_event_translator("load"),
            },
        }

    def detect_backend(self, target: Any) -> str:
        if hasattr(target, "script") and hasattr(target, "current_url"):
            return "selenium"
        if hasattr(target, "on") and hasattr(target, "remove_listener"):
            return "playwright"
        raise BidiBackendError(
            f"cannot detect backend for {type(target).__name__}"
        )

    def register_translator(self, backend: str, event: str, translator: Translator) -> None:
        self._translators.setdefault(backend, {})[event] = translator

    def subscribe(
        self,
        target: Any,
        event: str,
        callback: Callable[[BidiEvent], None],
        backend: Optional[str] = None,
    ) -> BidiSubscription:
        used_backend = backend or self.detect_backend(target)
        translator = self._translators.get(used_backend, {}).get(event)
        if translator is None:
            raise BidiBackendError(
                f"no translator for {used_backend}/{event!r}"
            )
        detach = translator(target, callback)
        sub = BidiSubscription(
            subscription_id=next(self._counter),
            event=event,
            backend=used_backend,
            detach=detach,
        )
        self._subscriptions[sub.subscription_id] = sub
        web_runner_logger.info(
            f"bidi subscribe id={sub.subscription_id} backend={used_backend} event={event!r}"
        )
        return sub

    def unsubscribe(self, subscription: BidiSubscription) -> None:
        subscription.unsubscribe()
        self._subscriptions.pop(subscription.subscription_id, None)

    def unsubscribe_all(self) -> None:
        for sub in list(self._subscriptions.values()):
            self.unsubscribe(sub)

    def active_subscriptions(self) -> List[BidiSubscription]:
        return list(self._subscriptions.values())
