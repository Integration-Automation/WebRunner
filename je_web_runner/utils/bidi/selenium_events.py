"""
Selenium 的 W3C BiDi 事件擷取、HAR 與回應模擬 / Event capture, HAR and response mocks over W3C BiDi.

Works on any Selenium driver started with BiDi (``webSocketUrl``; WebRunner's
``enable_bidi=True``), so Chrome and Firefox behave the same, where CDP would tie these
to Chromium. The Selenium twins of Playwright's event capture, HAR recording and route
mocking:

* console messages and JavaScript errors (``log.entryAdded``), network responses
  (``network.responseCompleted``) and DOM mutations (a preload ``MutationObserver``
  reporting over a ``script.message`` channel);
* a HAR 1.2 log built from ``network.beforeRequestSent`` / ``responseCompleted``
  (headers and timings; BiDi events carry no bodies);
* response mocks: each mock is a ``network.addIntercept`` on its URL pattern, so only
  matching requests are held; they are answered with ``network.provideResponse``.
  (Intercepting every request would hold the page's own document too, and chromedriver
  does not answer ``continueRequest`` while a classic ``get`` waits for that document.)

Every failure raises ``BidiEventsError``. Selenium runs each event callback on a thread
of its own, and its WebSocket connection numbers commands with an unguarded counter, so
two intercepted requests answered at once can collide and one of them then waits
forever. Every command this module sends goes through ``_BIDI_LOCK``.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from selenium.common.exceptions import WebDriverException

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.utils.observability.event_capture import EventCapture
from je_web_runner.webdriver.webdriver_wrapper import webdriver_wrapper_instance

_BIDI_LOCK = threading.Lock()
_DOM_CHANNEL = "webrunner-dom-mutations"
_DOM_OBSERVER = """(send) => {
  const describe = (node) => node && node.nodeName
    ? node.nodeName.toLowerCase() + (node.id ? '#' + node.id : '') : '';
  const observe = () => new MutationObserver((records) => {
    send(JSON.stringify(records.map((record) => ({
      type: record.type,
      target: describe(record.target),
      added: record.addedNodes ? record.addedNodes.length : 0,
      removed: record.removedNodes ? record.removedNodes.length : 0,
      attribute: record.attributeName || null,
    }))));
  }).observe(document, {childList: true, subtree: true, attributes: true, characterData: true});
  observe();
}"""


class BidiEventsError(WebRunnerException):
    """A BiDi capture, HAR or mock command could not run."""


class _RawEvent:
    """A BiDi event name for ``WebSocketConnection.add_callback``; callbacks get the params dict."""

    def __init__(self, event_class: str) -> None:
        self.event_class = event_class

    @staticmethod
    def from_json(params: dict[str, Any]) -> dict[str, Any]:
        """Hand the raw event params to the callback."""
        return params


def _command(method: str, params: dict[str, Any]) -> Any:
    from selenium.webdriver.common.bidi.common import command_builder
    return command_builder(method, params)


def _header_list(headers: Any) -> list[dict[str, str]]:
    """BiDi headers (``{name, value: {type, value}}``) as HAR ``{name, value}``."""
    converted = []
    for header in headers or []:
        value = header.get("value")
        converted.append({"name": header.get("name", ""),
                          "value": value.get("value", "") if isinstance(value, dict) else str(value or "")})
    return converted


def _iso(timestamp_ms: Any) -> str:
    if not isinstance(timestamp_ms, (int, float)):
        return datetime.now(timezone.utc).isoformat()
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).isoformat()


def _har_entry(request_params: dict[str, Any], response_params: dict[str, Any]) -> dict[str, Any]:
    request = request_params.get("request", {})
    response = response_params.get("response", {})
    started = request_params.get("timestamp")
    finished = response_params.get("timestamp")
    timed = isinstance(started, (int, float)) and isinstance(finished, (int, float))
    elapsed = max(0.0, float(finished - started)) if timed else 0.0
    return {
        "startedDateTime": _iso(started),
        "time": elapsed,
        "request": {
            "method": request.get("method", "GET"), "url": request.get("url", ""),
            "httpVersion": response.get("protocol", "") or "", "headers": _header_list(request.get("headers")),
            "queryString": [], "cookies": [], "headersSize": request.get("headersSize", -1) or -1,
            "bodySize": request.get("bodySize", -1) or -1,
        },
        "response": {
            "status": response.get("status", 0), "statusText": response.get("statusText", ""),
            "httpVersion": response.get("protocol", "") or "", "headers": _header_list(response.get("headers")),
            "cookies": [],
            "content": {"size": (response.get("content") or {}).get("size", -1),
                        "mimeType": response.get("mimeType", "")},
            "redirectURL": "", "headersSize": response.get("headersSize", -1) or -1,
            "bodySize": response.get("bodySize", -1) or -1,
        },
        "cache": {},
        "timings": {"send": 0, "wait": elapsed, "receive": 0},
    }


class SeleniumBidiEvents:
    """Event capture, HAR recording and response mocks for the current Selenium driver."""

    def __init__(self) -> None:
        self.capture = EventCapture()  # the same buffers and assertions as the Playwright capture
        self.dom_mutations: list[dict[str, Any]] = []
        self._capture_ids: list[tuple[str, Any, Any]] = []
        self._preload_id: str | None = None
        self._har_ids: list[tuple[Any, Any]] = []
        self._har_requests: dict[str, dict[str, Any]] = {}
        self._har_entries: list[dict[str, Any]] = []
        self._mocks: dict[str, tuple[str | dict[str, str], dict[str, Any]]] = {}  # intercept id -> mock
        self._mock_listener: tuple[Any, Any] | None = None

    # ----- plumbing ---------------------------------------------------------

    @staticmethod
    def _driver() -> Any:
        driver = webdriver_wrapper_instance.current_webdriver
        if driver is None:
            raise BidiEventsError("no Selenium driver is running")
        if not getattr(driver, "caps", {}).get("webSocketUrl"):
            raise BidiEventsError("the driver was started without BiDi; start it with enable_bidi=True")
        return driver

    def _listen(self, event_name: str, callback: Callable[[dict[str, Any]], None]) -> tuple[Any, Any]:
        conn = self._driver().network.conn
        event = _RawEvent(event_name)
        callback_id = conn.add_callback(event, callback)
        with _BIDI_LOCK:
            conn.execute(_command("session.subscribe", {"events": [event_name]}))
        return event, callback_id

    def _stop_listening(self, event: Any, callback_id: Any) -> None:
        conn = self._driver().network.conn
        conn.remove_callback(event, callback_id)
        with _BIDI_LOCK:
            conn.execute(_command("session.unsubscribe", {"events": [event.event_class]}))

    # ----- event capture ------------------------------------------------------

    def start_event_capture(self, dom_mutations: bool = False) -> None:
        """
        開始收集 console、JavaScript 錯誤與網路回應（可選 DOM 變動）
        Start collecting console messages, JavaScript errors (as ``error`` console
        entries), network responses and, with ``dom_mutations``, DOM mutations.
        """
        self.stop_event_capture()
        driver = self._driver()
        with _BIDI_LOCK:
            console_id = driver.script.add_console_message_handler(self._on_console)
            error_id = driver.script.add_javascript_error_handler(self._on_javascript_error)
        self._capture_ids = [("script", console_id, None), ("script", error_id, None)]
        event, callback_id = self._listen("network.responseCompleted", self._on_response)
        self._capture_ids.append(("event", event, callback_id))
        if dom_mutations:
            self._start_dom_mutations(driver)

    def _start_dom_mutations(self, driver: Any) -> None:
        event, callback_id = self._listen("script.message", self._on_script_message)
        self._capture_ids.append(("event", event, callback_id))
        channel = {"type": "channel", "value": {"channel": _DOM_CHANNEL, "ownership": "none"}}
        context = driver.current_window_handle
        with _BIDI_LOCK:
            self._preload_id = driver.script._add_preload_script(  # pylint: disable=protected-access
                _DOM_OBSERVER, arguments=[channel])
            driver.network.conn.execute(_command("script.callFunction", {
                "functionDeclaration": _DOM_OBSERVER, "arguments": [channel], "awaitPromise": False,
                "target": {"context": context},
            }))

    def stop_event_capture(self) -> None:
        """Stop collecting; what was collected stays until :meth:`clear_event_capture`."""
        if not self._capture_ids and self._preload_id is None:
            return
        driver = self._driver()
        for kind, first, second in self._capture_ids:
            if kind == "script":
                with _BIDI_LOCK:
                    driver.script.remove_console_message_handler(first)
            else:
                self._stop_listening(first, second)
        self._capture_ids = []
        if self._preload_id is not None:
            with _BIDI_LOCK:
                driver.script._remove_preload_script(self._preload_id)  # pylint: disable=protected-access
            self._preload_id = None

    def clear_event_capture(self) -> None:
        """Forget what was collected."""
        self.capture.clear()
        self.dom_mutations = []

    def console_messages(self) -> list[dict[str, Any]]:
        """``{type, text, location}`` per console message or JavaScript error collected."""
        return list(self.capture.console_messages)

    def network_responses(self) -> list[dict[str, Any]]:
        """``{url, status, method, ok}`` per response collected."""
        return list(self.capture.network_responses)

    def dom_mutation_records(self) -> list[dict[str, Any]]:
        """``{type, target, added, removed, attribute}`` per DOM mutation collected."""
        return list(self.dom_mutations)

    def _on_console(self, entry: Any) -> None:
        self.capture.console_messages.append({
            "type": getattr(entry, "level", None), "text": getattr(entry, "text", str(entry)), "location": None,
        })

    def _on_javascript_error(self, entry: Any) -> None:
        self.capture.console_messages.append({
            "type": "error", "text": getattr(entry, "text", str(entry)), "location": None,
        })

    def _on_response(self, params: dict[str, Any]) -> None:
        response = params.get("response", {})
        status = response.get("status", 0)
        self.capture.network_responses.append({
            "url": response.get("url") or params.get("request", {}).get("url"),
            "status": status, "method": params.get("request", {}).get("method"),
            "ok": 200 <= status < 400,
        })

    def _on_script_message(self, params: dict[str, Any]) -> None:
        if params.get("channel") != _DOM_CHANNEL:
            return
        data = params.get("data", {})
        try:
            self.dom_mutations.extend(json.loads(data.get("value", "[]")))
        except (TypeError, ValueError) as error:
            web_runner_logger.warning(f"bidi dom mutation message unreadable: {error!r}")

    # ----- HAR -------------------------------------------------------------

    def start_har_recording(self) -> None:
        """Start recording every request and response of the driver into a HAR log."""
        self.stop_har_recording(None)
        self._har_requests, self._har_entries = {}, []
        self._har_ids = [
            self._listen("network.beforeRequestSent", self._on_har_request),
            self._listen("network.responseCompleted", self._on_har_response),
        ]

    def stop_har_recording(self, har_path: str | None) -> str | None:
        """Stop recording and write the HAR 1.2 log to ``har_path`` (nothing is written for None)."""
        for event, callback_id in self._har_ids:
            self._stop_listening(event, callback_id)
        self._har_ids = []
        if har_path is None:
            return None
        log = {"log": {"version": "1.2", "creator": {"name": "WebRunner", "version": "1"},
                       "pages": [], "entries": list(self._har_entries)}}
        Path(har_path).parent.mkdir(parents=True, exist_ok=True)
        Path(har_path).write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
        return har_path

    def _on_har_request(self, params: dict[str, Any]) -> None:
        request_id = params.get("request", {}).get("request")
        if request_id:
            self._har_requests[request_id] = params

    def _on_har_response(self, params: dict[str, Any]) -> None:
        request_id = params.get("request", {}).get("request")
        request_params = self._har_requests.pop(request_id, None) or {"request": params.get("request", {})}
        self._har_entries.append(_har_entry(request_params, params))

    # ----- response mocks ----------------------------------------------------

    def route_mock(self, url_pattern: str | dict[str, str], response: dict[str, Any]) -> None:
        """
        以固定回應回答符合 pattern 的請求
        Answer requests matching ``url_pattern`` with ``response`` (``status``, ``body``
        text, ``headers`` dict, ``content_type``). ``url_pattern`` is an exact URL,
        ``*/path`` or ``**/path`` (that path on any host), or a dict of URL parts
        (``protocol``, ``hostname``, ``port``, ``pathname``, ``search``). Each mock is its
        own BiDi intercept, so only matching requests wait for an answer; a mock that
        matched the page's own document would block the navigation that loads it.
        """
        bidi_pattern = to_bidi_url_pattern(url_pattern)
        try:
            _provide_params(None, response)
        except (TypeError, ValueError, AttributeError) as error:
            raise BidiEventsError(f"unusable mock response {response!r}: {error!r}") from error
        with _BIDI_LOCK:
            result = self._driver().network.conn.execute(_command(
                "network.addIntercept", {"phases": ["beforeRequestSent"], "urlPatterns": [bidi_pattern]}))
        self._mocks[result["intercept"]] = (url_pattern, dict(response))
        if self._mock_listener is None:
            self._mock_listener = self._listen("network.beforeRequestSent", self._on_request_sent)

    def route_mock_json(self, url_pattern: str | dict[str, str], json_data: Any, status: int = 200) -> None:
        """A :meth:`route_mock` answering with ``json_data`` as JSON."""
        self.route_mock(url_pattern, {"status": status, "body": json.dumps(json_data),
                                      "content_type": "application/json"})

    def route_unmock(self, url_pattern: str | dict[str, str]) -> None:
        """Remove the mocks registered for ``url_pattern``."""
        for intercept, (pattern, _response) in list(self._mocks.items()):
            if pattern == url_pattern:
                self._remove_mock(intercept)
        if not self._mocks:
            self._stop_mock_listener()

    def route_clear(self) -> None:
        """Remove every mock and stop intercepting."""
        for intercept in list(self._mocks):
            self._remove_mock(intercept)
        self._stop_mock_listener()

    def _remove_mock(self, intercept: str) -> None:
        del self._mocks[intercept]
        with _BIDI_LOCK:
            self._driver().network.conn.execute(_command("network.removeIntercept", {"intercept": intercept}))

    def _stop_mock_listener(self) -> None:
        if self._mock_listener is not None:
            listener, self._mock_listener = self._mock_listener, None
            self._stop_listening(*listener)

    def _on_request_sent(self, params: dict[str, Any]) -> None:
        if not params.get("isBlocked"):
            return
        ours = [intercept for intercept in params.get("intercepts") or [] if intercept in self._mocks]
        if not ours:
            return
        request_id = params.get("request", {}).get("request")
        _pattern, mock = self._mocks[ours[-1]]
        conn = self._driver().network.conn
        with _BIDI_LOCK:
            try:
                conn.execute(_command("network.provideResponse", _provide_params(request_id, mock)))
            except (WebDriverException, KeyError) as error:  # an unanswered request would hang the page
                web_runner_logger.error(f"bidi route mock failed for {params.get('request', {}).get('url')!r}: "
                                        f"{error!r}")
                conn.execute(_command("network.continueRequest", {"request": request_id}))


def to_bidi_url_pattern(url_pattern: str | dict[str, str]) -> dict[str, Any]:
    """
    把 mock 的 pattern 轉成 BiDi ``UrlPattern``
    An exact URL becomes a ``string`` pattern; ``*/path`` / ``**/path`` become a
    ``pattern`` on that path for any host; a dict of URL parts is used as given.
    """
    if isinstance(url_pattern, dict):
        unknown = set(url_pattern) - {"protocol", "hostname", "port", "pathname", "search"}
        if unknown:
            raise BidiEventsError(f"unknown URL pattern parts {sorted(unknown)}")
        return {"type": "pattern", **{key: str(value) for key, value in url_pattern.items()}}
    if not isinstance(url_pattern, str) or not url_pattern:
        raise BidiEventsError("url_pattern must be a URL, '*/path', or a dict of URL parts")
    for prefix in ("**/", "*/"):
        if url_pattern.startswith(prefix):
            path = "/" + url_pattern[len(prefix):]
            if "*" in path:
                raise BidiEventsError(f"only a leading '*/' is supported in {url_pattern!r}")
            return {"type": "pattern", "pathname": path}
    if "*" in url_pattern:
        raise BidiEventsError(f"use an exact URL, '*/path' or a dict of URL parts, not {url_pattern!r}")
    return {"type": "string", "pattern": url_pattern}


def _provide_params(request_id: Any, mock: dict[str, Any]) -> dict[str, Any]:
    headers = dict(mock.get("headers") or {})
    if mock.get("content_type"):
        headers.setdefault("Content-Type", mock["content_type"])
    return {
        "request": request_id,
        "statusCode": int(mock.get("status", 200)),
        "reasonPhrase": str(mock.get("reason", "OK")),
        "headers": [{"name": name, "value": {"type": "string", "value": str(value)}}
                    for name, value in headers.items()],
        "body": {"type": "string", "value": str(mock.get("body", ""))},
    }


selenium_bidi_events = SeleniumBidiEvents()
