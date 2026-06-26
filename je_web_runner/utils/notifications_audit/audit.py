"""
追蹤 `Notification.requestPermission()` 的呼叫時機 + 顯示的 notifications。
Browsers shame UX bugs around notifications (auto-prompt on page load,
spam after rejection, prompt without user gesture). This module installs
a JS shim that records every permission request and every ``new
Notification(...)`` call, then exposes asserts for common policy
violations.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

from je_web_runner.utils.exception.exceptions import WebRunnerException


class NotificationsAuditError(WebRunnerException):
    """Raised on malformed harvest payload / failed assertion."""


class PermissionResult(str, Enum):
    GRANTED = "granted"
    DENIED = "denied"
    DEFAULT = "default"


# ---------- model -------------------------------------------------------

@dataclass
class PermissionRequest:
    """One ``Notification.requestPermission`` call."""

    timestamp_ms: float
    user_gesture: bool
    result: PermissionResult
    page_age_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "result": self.result.value}


@dataclass
class NotificationShown:
    """One ``new Notification(...)`` call."""

    timestamp_ms: float
    title: str
    body: str = ""
    tag: str | None = None
    require_interaction: bool = False
    silent: bool = False


@dataclass
class NotificationsLog:
    """Combined audit log."""

    permission_requests: list[PermissionRequest] = field(default_factory=list)
    notifications: list[NotificationShown] = field(default_factory=list)


# ---------- script generation ------------------------------------------

_INSTALL_TEMPLATE = """
(function() {
  if (window.__wr_notif_installed__) return;
  window.__wr_notif_installed__ = true;
  window.__wr_notif_log__ = {permission_requests: [], notifications: []};
  const pageStart = performance.now();

  let lastGesture = 0;
  ['click', 'keydown', 'pointerup', 'touchend'].forEach(function(t) {
    document.addEventListener(t, function() {
      lastGesture = performance.now();
    }, true);
  });

  const _realRequest = Notification && Notification.requestPermission
    ? Notification.requestPermission.bind(Notification)
    : null;
  if (_realRequest) {
    Notification.requestPermission = function() {
      const ts = performance.now();
      const withinGesture = (ts - lastGesture) < 1000;
      return _realRequest().then(function(result) {
        window.__wr_notif_log__.permission_requests.push({
          timestamp_ms: ts,
          user_gesture: withinGesture,
          result: String(result),
          page_age_ms: ts - pageStart
        });
        return result;
      });
    };
  }

  const _RealNotification = window.Notification;
  if (_RealNotification) {
    function FakeNotification(title, opts) {
      opts = opts || {};
      window.__wr_notif_log__.notifications.push({
        timestamp_ms: performance.now(),
        title: String(title || ''),
        body: String(opts.body || ''),
        tag: opts.tag != null ? String(opts.tag) : null,
        require_interaction: !!opts.requireInteraction,
        silent: !!opts.silent
      });
      return new _RealNotification(title, opts);
    }
    FakeNotification.permission = _RealNotification.permission;
    FakeNotification.requestPermission = Notification.requestPermission;
    Object.setPrototypeOf(FakeNotification, _RealNotification);
    window.Notification = FakeNotification;
  }
})();
""".strip()


def build_install_script() -> str:
    return _INSTALL_TEMPLATE


HARVEST_SCRIPT = "return window.__wr_notif_log__ || {permission_requests: [], notifications: []};"


# ---------- parsing ----------------------------------------------------

def parse_log(payload: Any) -> NotificationsLog:  # NOSONAR S3776 — cohesive logic; planned refactor in follow-up
    """Convert the harvested JSON into typed records."""
    if not isinstance(payload, dict):
        raise NotificationsAuditError(
            f"payload must be dict, got {type(payload).__name__}"
        )
    requests: list[PermissionRequest] = []
    for raw in payload.get("permission_requests") or []:
        if not isinstance(raw, dict):
            continue
        try:
            result = PermissionResult(str(raw.get("result") or "default"))
        except ValueError:
            result = PermissionResult.DEFAULT
        try:
            requests.append(PermissionRequest(
                timestamp_ms=float(raw.get("timestamp_ms") or 0),
                user_gesture=bool(raw.get("user_gesture", False)),
                result=result,
                page_age_ms=float(raw.get("page_age_ms") or 0),
            ))
        except (TypeError, ValueError) as error:
            raise NotificationsAuditError(
                f"bad permission_request entry {raw!r}: {error}"
            ) from error
    notifications: list[NotificationShown] = []
    for raw in payload.get("notifications") or []:
        if not isinstance(raw, dict):
            continue
        try:
            notifications.append(NotificationShown(
                timestamp_ms=float(raw.get("timestamp_ms") or 0),
                title=str(raw.get("title") or ""),
                body=str(raw.get("body") or ""),
                tag=raw.get("tag"),
                require_interaction=bool(raw.get("require_interaction", False)),
                silent=bool(raw.get("silent", False)),
            ))
        except (TypeError, ValueError) as error:
            raise NotificationsAuditError(
                f"bad notification entry {raw!r}: {error}"
            ) from error
    return NotificationsLog(
        permission_requests=requests,
        notifications=notifications,
    )


# ---------- assertions -------------------------------------------------

def assert_no_prompt_without_gesture(log: NotificationsLog) -> None:
    """Assert every permission request happened within a user-gesture window."""
    for req in log.permission_requests:
        if not req.user_gesture:
            raise NotificationsAuditError(
                f"Notification.requestPermission called without user gesture "
                f"at page age {req.page_age_ms:.0f}ms"
            )


def assert_no_prompt_before(
    log: NotificationsLog,
    *,
    min_page_age_ms: float,
) -> None:
    """Assert no prompt fires before ``min_page_age_ms`` (avoids auto-prompt on load)."""
    if min_page_age_ms < 0:
        raise NotificationsAuditError("min_page_age_ms must be >= 0")
    for req in log.permission_requests:
        if req.page_age_ms < min_page_age_ms:
            raise NotificationsAuditError(
                f"prompt fired at {req.page_age_ms:.0f}ms, want >= {min_page_age_ms}ms"
            )


def assert_no_spam_after_deny(log: NotificationsLog) -> None:
    """Assert no further prompts or notifications appear after a 'denied'."""
    deny_time: float | None = None
    for req in log.permission_requests:
        if req.result == PermissionResult.DENIED:
            deny_time = req.timestamp_ms
            continue
        if deny_time is not None and req.timestamp_ms > deny_time:
            raise NotificationsAuditError(
                f"re-prompted after denial at {req.timestamp_ms:.0f}ms"
            )
    if deny_time is None:
        return
    for notif in log.notifications:
        if notif.timestamp_ms > deny_time:
            raise NotificationsAuditError(
                f"notification shown after denial: {notif.title!r}"
            )


def assert_notification_shown(
    log: NotificationsLog,
    *,
    title_contains: str | None = None,
    body_contains: str | None = None,
    tag: str | None = None,
) -> NotificationShown:
    """Assert at least one notification matches the given filters."""
    if title_contains is None and body_contains is None and tag is None:
        raise NotificationsAuditError(
            "provide at least one of title_contains / body_contains / tag"
        )
    for notif in log.notifications:
        if title_contains is not None and title_contains not in notif.title:
            continue
        if body_contains is not None and body_contains not in notif.body:
            continue
        if tag is not None and notif.tag != tag:
            continue
        return notif
    raise NotificationsAuditError(
        f"no notification matched title_contains={title_contains!r} "
        f"body_contains={body_contains!r} tag={tag!r}"
    )


def assert_unique_tags(log: NotificationsLog) -> None:
    """Assert no tag was reused (would silently replace earlier notification)."""
    seen: dict[str, int] = {}
    for notif in log.notifications:
        if notif.tag is None:
            continue
        seen[notif.tag] = seen.get(notif.tag, 0) + 1
    duplicates = [tag for tag, count in seen.items() if count > 1]
    if duplicates:
        raise NotificationsAuditError(
            f"notification tags reused: {sorted(duplicates)}"
        )
