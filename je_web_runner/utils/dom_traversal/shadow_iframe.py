"""
穿透 Shadow DOM 與多層 iframe 的輔助命令。
Helpers to pierce Shadow DOM roots and navigate nested iframes on both
backends.
"""
from __future__ import annotations

from typing import Any, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.webdriver.playwright_wrapper import playwright_wrapper_instance
from je_web_runner.webdriver.webdriver_wrapper import webdriver_wrapper_instance


class DOMTraversalError(WebRunnerException):
    """Raised when traversal cannot complete."""


_NO_SELENIUM_DRIVER = "no Selenium driver active"


# Walk down a chain of host selectors, then run the final selector inside
# the deepest shadow root. Returns the matched element or None.
_SHADOW_QUERY_JS = r"""
function pierce(hosts, inner) {
  var ctx = document;
  for (var i = 0; i < hosts.length; i++) {
    var host = ctx.querySelector(hosts[i]);
    if (!host || !host.shadowRoot) return null;
    ctx = host.shadowRoot;
  }
  return ctx.querySelector(inner);
}
return pierce(arguments[0], arguments[1]);
"""


def selenium_query_in_shadow(host_chain: Sequence[str], inner_selector: str) -> Any:
    """
    在巢狀 Shadow DOM 中查詢
    Walk ``host_chain`` (each element is a CSS selector for the next shadow
    host) and return the element matching ``inner_selector`` inside the
    deepest shadow root.
    """
    web_runner_logger.info(
        f"selenium_query_in_shadow chain={list(host_chain)} inner={inner_selector!r}"
    )
    driver = webdriver_wrapper_instance.current_webdriver
    if driver is None:
        raise DOMTraversalError(_NO_SELENIUM_DRIVER)
    return driver.execute_script(_SHADOW_QUERY_JS, list(host_chain), inner_selector)


def playwright_shadow_selector(host_chain: Sequence[str], inner_selector: str) -> str:
    """
    把 host 鏈與內層 selector 組成 Playwright ``>>>`` (pierce) 選擇器
    Compose a Playwright ``>>>`` selector that pierces shadow roots, e.g.
    ``my-app >>> my-button >>> button.primary``.
    """
    return " >>> ".join([*list(host_chain), inner_selector])


def playwright_query_in_shadow(host_chain: Sequence[str], inner_selector: str):
    """Resolve the pierce selector against the active Playwright page."""
    return playwright_wrapper_instance.page.query_selector(
        playwright_shadow_selector(host_chain, inner_selector)
    )


def selenium_switch_iframe_chain(selectors: Sequence[str]) -> None:
    """
    依序切換進入多層 iframe（每層用 CSS selector 指定）
    Walk ``selectors`` and switch into each iframe in turn. Call
    ``selenium_back_to_default`` to return to the top frame.
    """
    web_runner_logger.info(f"selenium_switch_iframe_chain: {list(selectors)}")
    driver = webdriver_wrapper_instance.current_webdriver
    if driver is None:
        raise DOMTraversalError(_NO_SELENIUM_DRIVER)
    driver.switch_to.default_content()
    for selector in selectors:
        frame = driver.find_element("css selector", selector)
        driver.switch_to.frame(frame)


def selenium_back_to_default() -> None:
    """Return Selenium focus to the top-level frame."""
    driver = webdriver_wrapper_instance.current_webdriver
    if driver is None:
        raise DOMTraversalError(_NO_SELENIUM_DRIVER)
    driver.switch_to.default_content()


def playwright_frame_locator_chain(selectors: Sequence[str]) -> Any:
    """
    依序連結 ``page.frame_locator(selector)`` 形成深層 frame locator
    Chain ``page.frame_locator(...)`` calls and return the deepest
    ``FrameLocator``. Use the result for further ``.locator(...)`` calls.
    """
    locator = playwright_wrapper_instance.page
    for selector in selectors:
        locator = locator.frame_locator(selector)
    return locator
