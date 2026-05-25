"""
Web Push (VAPID) subscription & delivery assertions.

The browser side captures every ``PushManager.subscribe``,
``pushsubscriptionchange``, and ``showNotification`` call.
The Python side validates:

* The subscription was created with the right application server key
  (VAPID public key).
* The endpoint URL looks like a real push service
  (``fcm.googleapis.com`` / ``mozilla.com`` / ``windows.com``).
* The page eventually called ``registration.showNotification`` with a
  body that matches the expected push payload.
* User-Visible-Only is set to ``true`` (browsers reject otherwise).
"""
from __future__ import annotations

import base64
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence
from urllib.parse import urlparse

from je_web_runner.utils.exception.exceptions import WebRunnerException


class WebPushAssertError(WebRunnerException):
    """Raised on malformed input or assertion failure."""


INSTALL_SCRIPT = r"""
(function () {
  if (window.__wr_push__) return;
  const subs = [];
  const shown = [];
  if (navigator.serviceWorker) {
    navigator.serviceWorker.ready.then((reg) => {
      if (reg.pushManager) {
        const origSub = reg.pushManager.subscribe.bind(reg.pushManager);
        reg.pushManager.subscribe = function (opts) {
          subs.push({
            applicationServerKey: opts && opts.applicationServerKey
              ? (typeof opts.applicationServerKey === 'string'
                  ? opts.applicationServerKey
                  : btoa(String.fromCharCode.apply(null,
                    new Uint8Array(opts.applicationServerKey))))
              : '',
            userVisibleOnly: opts && opts.userVisibleOnly,
          });
          return origSub(opts);
        };
      }
      const origShow = reg.showNotification.bind(reg);
      reg.showNotification = function (title, opts) {
        shown.push({title, body: (opts && opts.body) || '',
                    tag: (opts && opts.tag) || ''});
        return origShow(title, opts);
      };
    });
  }
  window.__wr_push__ = {
    drainSubs: function () { return subs.splice(0); },
    drainShown: function () { return shown.splice(0); },
  };
})();
"""


_KNOWN_PUSH_HOSTS = (
    "fcm.googleapis.com", "updates.push.services.mozilla.com",
    "wns2-bn3p.notify.windows.com", "wns2-am3p.notify.windows.com",
    "web.push.apple.com",
)


@dataclass
class Subscription:
    application_server_key: str = ""
    user_visible_only: bool = False
    endpoint: str = ""


@dataclass
class Notification:
    title: str = ""
    body: str = ""
    tag: str = ""


@dataclass
class PushLog:
    subscriptions: List[Subscription] = field(default_factory=list)
    notifications: List[Notification] = field(default_factory=list)


def parse_log(payload: Any) -> PushLog:
    if not isinstance(payload, dict):
        raise WebPushAssertError("payload must be a dict")
    subs: List[Subscription] = []
    for raw in payload.get("subscriptions") or []:
        if not isinstance(raw, dict):
            continue
        subs.append(Subscription(
            application_server_key=str(raw.get("applicationServerKey") or ""),
            user_visible_only=bool(raw.get("userVisibleOnly")),
            endpoint=str(raw.get("endpoint") or ""),
        ))
    notes: List[Notification] = []
    for raw in payload.get("notifications") or []:
        if not isinstance(raw, dict):
            continue
        notes.append(Notification(
            title=str(raw.get("title") or ""),
            body=str(raw.get("body") or ""),
            tag=str(raw.get("tag") or ""),
        ))
    return PushLog(subscriptions=subs, notifications=notes)


def _normalize_b64(value: str) -> str:
    # Accept urlsafe vs standard base64 + missing padding
    cleaned = value.replace("-", "+").replace("_", "/")
    cleaned += "=" * (-len(cleaned) % 4)
    return cleaned


def assert_subscribed_with_vapid(
    log: PushLog, *, vapid_public_key: str,
) -> None:
    if not vapid_public_key:
        raise WebPushAssertError("vapid_public_key must be non-empty")
    if not log.subscriptions:
        raise WebPushAssertError("page never called pushManager.subscribe()")
    expected = _normalize_b64(vapid_public_key)
    for sub in log.subscriptions:
        actual = _normalize_b64(sub.application_server_key)
        if actual != expected:
            raise WebPushAssertError(
                f"subscription used wrong VAPID key: got "
                f"{sub.application_server_key[:12]!r}…, "
                f"expected {vapid_public_key[:12]!r}…"
            )


def assert_user_visible_only(log: PushLog) -> None:
    for sub in log.subscriptions:
        if not sub.user_visible_only:
            raise WebPushAssertError(
                "subscription created without userVisibleOnly=true "
                "(Chrome will reject this)"
            )


def assert_endpoint_recognised(log: PushLog) -> None:
    for sub in log.subscriptions:
        if not sub.endpoint:
            continue   # endpoint only populated after Push service returns
        host = urlparse(sub.endpoint).hostname or ""
        if not any(host == known or host.endswith("." + known)
                   for known in _KNOWN_PUSH_HOSTS):
            raise WebPushAssertError(
                f"unrecognised push service host: {host!r} "
                f"(expected one of {_KNOWN_PUSH_HOSTS})"
            )


def assert_notification_shown(
    log: PushLog, *, body_contains: str = "",
) -> Notification:
    if not log.notifications:
        raise WebPushAssertError(
            "page received push but never called showNotification()"
        )
    if not body_contains:
        return log.notifications[0]
    for n in log.notifications:
        if body_contains in n.body or body_contains in n.title:
            return n
    raise WebPushAssertError(
        f"no notification body/title contained {body_contains!r}"
    )
