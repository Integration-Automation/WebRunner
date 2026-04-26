"""
Shadow DOM auto-pierce：遞迴穿透開放 shadow root 找元件，Selenium / Playwright 共用 API。
Recursive shadow-DOM piercing helper. Selenium needs JS to traverse open
shadow roots; Playwright supports the ``>>`` selector natively, but the
helper here normalises both backends to one ``find_first(driver, css)``
call.

The piercing is performed in JavaScript so it works against any
Chromium / Firefox / WebKit page exposing ``shadowRoot.mode === "open"``.
"""
from __future__ import annotations

from typing import Any, List

from je_web_runner.utils.exception.exceptions import WebRunnerException


class ShadowPierceError(WebRunnerException):
    """Raised when the driver doesn't expose a JS evaluation surface."""


_PIERCE_FIRST_JS = r"""
(() => {
  const target = arguments[0];
  const stack = [document];
  while (stack.length) {
    const root = stack.pop();
    const found = root.querySelector(target);
    if (found) return found;
    const candidates = root.querySelectorAll('*');
    for (const node of candidates) {
      if (node.shadowRoot && node.shadowRoot.mode === 'open') {
        stack.push(node.shadowRoot);
      }
    }
  }
  return null;
})()
"""


_PIERCE_ALL_JS = r"""
(() => {
  const target = arguments[0];
  const limit = arguments[1] || 1000;
  const matches = [];
  const stack = [document];
  while (stack.length && matches.length < limit) {
    const root = stack.pop();
    root.querySelectorAll(target).forEach((node) => {
      if (matches.length < limit) {
        matches.push(node);
      }
    });
    root.querySelectorAll('*').forEach((node) => {
      if (node.shadowRoot && node.shadowRoot.mode === 'open') {
        stack.push(node.shadowRoot);
      }
    });
  }
  return matches;
})()
"""


def _execute_js(driver: Any, script: str, *args: Any) -> Any:
    if hasattr(driver, "execute_script"):
        # Selenium passes args via ``arguments[0]``; rewrite the body for that.
        wrapped = "var arguments = [...arguments];\n" + script
        return driver.execute_script(wrapped, *args)
    if hasattr(driver, "evaluate"):
        # Playwright: convert the script into an arrow function over ``args``.
        wrapped = (
            "(args) => {"
            "  const arguments = args; "
            f" return ({script});"
            "}"
        )
        return driver.evaluate(wrapped, list(args))
    raise ShadowPierceError("driver has neither execute_script nor evaluate")


def find_first(driver: Any, css_selector: str) -> Any:
    """
    從 ``document`` 起遞迴穿透 open shadow roots 找第一個符合 CSS 選擇器的節點。
    Return the first node matching ``css_selector`` anywhere in the
    document, walking through open shadow roots. ``None`` when no match.
    """
    if not isinstance(css_selector, str) or not css_selector:
        raise ShadowPierceError("css_selector must be a non-empty string")
    return _execute_js(driver, _PIERCE_FIRST_JS, css_selector)


def find_all(driver: Any, css_selector: str, limit: int = 1000) -> List[Any]:
    """Return up to ``limit`` matching nodes across the shadow tree."""
    if not isinstance(css_selector, str) or not css_selector:
        raise ShadowPierceError("css_selector must be a non-empty string")
    if limit <= 0:
        raise ShadowPierceError("limit must be > 0")
    result = _execute_js(driver, _PIERCE_ALL_JS, css_selector, limit)
    if result is None:
        return []
    return list(result)


def assert_pierced_visible(driver: Any, css_selector: str) -> None:
    """Raise unless at least one matching node is found in the shadow tree."""
    found = find_first(driver, css_selector)
    if found is None:
        raise ShadowPierceError(
            f"selector {css_selector!r} not found in any open shadow root"
        )
