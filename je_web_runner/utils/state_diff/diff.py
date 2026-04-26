"""
Browser state diff：在 test 前後 snapshot cookies / localStorage / sessionStorage，
列出每個 key 的 added / removed / changed 變化，方便 debug 認證 / cart-state 流程。
Capture and diff browser state snapshots. Selenium / Playwright share
the same probing surface (cookies via the driver API, storage via JS),
so the helpers below detect the backend at runtime.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Optional, Tuple

from je_web_runner.utils.exception.exceptions import WebRunnerException


class StateDiffError(WebRunnerException):
    """Raised when capture / diff input is invalid."""


@dataclass
class BrowserStateSnapshot:
    """One snapshot of cookies + localStorage + sessionStorage."""

    cookies: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    local_storage: Dict[str, str] = field(default_factory=dict)
    session_storage: Dict[str, str] = field(default_factory=dict)


@dataclass
class StateChanges:
    added: Dict[str, Any] = field(default_factory=dict)
    removed: Dict[str, Any] = field(default_factory=dict)
    changed: Dict[str, Tuple[Any, Any]] = field(default_factory=dict)

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.removed or self.changed)


@dataclass
class StateDiff:
    cookies: StateChanges = field(default_factory=StateChanges)
    local_storage: StateChanges = field(default_factory=StateChanges)
    session_storage: StateChanges = field(default_factory=StateChanges)

    @property
    def has_changes(self) -> bool:
        return any(
            section.has_changes
            for section in (self.cookies, self.local_storage, self.session_storage)
        )


def _diff_dicts(before: Dict[str, Any], after: Dict[str, Any]) -> StateChanges:
    before_keys = set(before.keys())
    after_keys = set(after.keys())
    changes = StateChanges()
    for key in after_keys - before_keys:
        changes.added[key] = after[key]
    for key in before_keys - after_keys:
        changes.removed[key] = before[key]
    for key in before_keys & after_keys:
        if before[key] != after[key]:
            changes.changed[key] = (before[key], after[key])
    return changes


def diff_states(before: BrowserStateSnapshot, after: BrowserStateSnapshot) -> StateDiff:
    if not isinstance(before, BrowserStateSnapshot) or not isinstance(after, BrowserStateSnapshot):
        raise StateDiffError("inputs must be BrowserStateSnapshot")
    return StateDiff(
        cookies=_diff_dicts(before.cookies, after.cookies),
        local_storage=_diff_dicts(before.local_storage, after.local_storage),
        session_storage=_diff_dicts(before.session_storage, after.session_storage),
    )


_LS_DUMP_JS = (
    "(() => {"
    "  const out = {};"
    "  for (let i = 0; i < localStorage.length; i++) {"
    "    const k = localStorage.key(i);"
    "    out[k] = localStorage.getItem(k);"
    "  } return out;"
    "})()"
)


_SS_DUMP_JS = (
    "(() => {"
    "  const out = {};"
    "  for (let i = 0; i < sessionStorage.length; i++) {"
    "    const k = sessionStorage.key(i);"
    "    out[k] = sessionStorage.getItem(k);"
    "  } return out;"
    "})()"
)


def _execute_js(driver: Any, expression: str) -> Any:
    if hasattr(driver, "execute_script"):
        return driver.execute_script(f"return {expression};")
    if hasattr(driver, "evaluate"):
        return driver.evaluate(expression)
    raise StateDiffError("driver has neither execute_script nor evaluate")


def _selenium_cookies(driver: Any) -> Dict[str, Dict[str, Any]]:
    if not hasattr(driver, "get_cookies"):
        return {}
    cookies = driver.get_cookies() or []
    return {
        str(c.get("name")): dict(c)
        for c in cookies
        if isinstance(c, dict) and c.get("name")
    }


def _playwright_cookies(driver: Any) -> Dict[str, Dict[str, Any]]:
    context = getattr(driver, "context", None)
    if context is None or not hasattr(context, "cookies"):
        return {}
    cookies = context.cookies() or []
    return {
        str(c.get("name")): dict(c)
        for c in cookies
        if isinstance(c, dict) and c.get("name")
    }


def capture_state(driver: Any) -> BrowserStateSnapshot:
    """
    抓 driver 當下的 cookies + localStorage + sessionStorage
    Take a snapshot. Selenium drivers expose ``get_cookies`` directly;
    Playwright pages expose them on ``page.context.cookies()``.
    """
    if hasattr(driver, "get_cookies"):
        cookies = _selenium_cookies(driver)
    elif hasattr(driver, "context"):
        cookies = _playwright_cookies(driver)
    else:
        raise StateDiffError("driver has neither get_cookies nor context.cookies()")
    local_storage = _execute_js(driver, _LS_DUMP_JS) or {}
    session_storage = _execute_js(driver, _SS_DUMP_JS) or {}
    if not isinstance(local_storage, dict) or not isinstance(session_storage, dict):
        raise StateDiffError("storage probe returned non-object")
    return BrowserStateSnapshot(
        cookies=cookies,
        local_storage={str(k): str(v) for k, v in local_storage.items()},
        session_storage={str(k): str(v) for k, v in session_storage.items()},
    )


def assert_no_state_change(diff: StateDiff,
                           allow_keys: Optional[Iterable[str]] = None) -> None:
    """Raise if the diff has any change outside ``allow_keys``."""
    allow = set(allow_keys or [])
    bad = []
    for section_name, section in (
        ("cookies", diff.cookies),
        ("local_storage", diff.local_storage),
        ("session_storage", diff.session_storage),
    ):
        for key in tuple(section.added.keys()) + tuple(section.removed.keys()) + tuple(section.changed.keys()):
            if key not in allow:
                bad.append((section_name, key))
    if bad:
        raise StateDiffError(f"unexpected state change(s): {bad[:5]}")
