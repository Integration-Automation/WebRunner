"""
Selenium 對應 Playwright 的命令 / Selenium commands matching Playwright ones.

Waits usable from action JSON, finding by a raw selector, JavaScript dialogs, named
device presets, permissions and a frozen clock. Unlike the older wrapper methods these
raise on failure (after recording it), so a failed wait or a missing alert fails its
action, as the Playwright twins do.
"""
from __future__ import annotations

from typing import Any

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait

from je_web_runner.element.web_element_wrapper import web_element_wrapper
from je_web_runner.utils.device_emulation.presets import available_presets, cdp_emulation_command, get_preset
from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.test_record.recorded import recorded_calls
from je_web_runner.utils.time_freezer.freezer import build_freezer_script, freeze_at

recorded = recorded_calls("webdriver wrapper")

_WAIT_STATES = {
    "present": expected_conditions.presence_of_element_located,
    "visible": expected_conditions.visibility_of_element_located,
    "clickable": expected_conditions.element_to_be_clickable,
    "hidden": expected_conditions.invisibility_of_element_located,
}
# Playwright permission names -> Chrome DevTools ``PermissionType``; CDP names pass through.
_PERMISSIONS = {
    "geolocation": "geolocation", "notifications": "notifications", "midi": "midi",
    "camera": "videoCapture", "microphone": "audioCapture",
    "clipboard-read": "clipboardReadWrite", "clipboard-write": "clipboardSanitizedWrite",
    "background-sync": "backgroundSync", "accelerometer": "sensors", "gyroscope": "sensors",
    "magnetometer": "sensors", "ambient-light-sensor": "sensors", "payment-handler": "paymentHandler",
}


def resolve_by(by: str) -> str:
    """A Selenium ``By`` value from ``"css selector"`` / ``"CSS_SELECTOR"`` / ``"xpath"`` …"""
    values = {value for name, value in vars(By).items() if not name.startswith("_") and isinstance(value, str)}
    if by in values:
        return by
    value = getattr(By, str(by).upper(), None)
    if isinstance(value, str):
        return value
    raise WebRunnerException(f"unknown locator strategy {by!r}; use one of {sorted(values)}")


class _ParityMixin:
    """Commands the Playwright backend had and the Selenium one did not."""

    # ----- waits ---------------------------------------------------------

    @recorded
    def wait_for_element(self, selector: str, by: str = "css selector", timeout: float = 10.0,
                         state: str = "visible") -> Any:
        """
        等元素出現（``present`` / ``visible`` / ``clickable``）或消失（``hidden``）
        Wait up to ``timeout`` seconds for the element to reach ``state``. For
        ``present``, ``visible`` and ``clickable`` the element becomes the current
        element (for the ``WR_element_*`` commands) and is returned.
        """
        if state not in _WAIT_STATES:
            raise WebRunnerException(f"wait state must be one of {sorted(_WAIT_STATES)}, not {state!r}")
        condition = _WAIT_STATES[state]((resolve_by(by), selector))
        result = WebDriverWait(self.current_webdriver, timeout).until(condition)
        if state != "hidden":
            web_element_wrapper.current_web_element = result
        return result

    @recorded
    def wait_for_url(self, pattern: str, timeout: float = 10.0) -> bool:
        """Wait until the current URL contains ``pattern``."""
        return WebDriverWait(self.current_webdriver, timeout).until(expected_conditions.url_contains(pattern))

    @recorded
    def wait_for_title(self, pattern: str, timeout: float = 10.0) -> bool:
        """Wait until the page title contains ``pattern``."""
        return WebDriverWait(self.current_webdriver, timeout).until(expected_conditions.title_contains(pattern))

    @recorded
    def wait_for_ready_state(self, timeout: float = 30.0) -> bool:
        """Wait until ``document.readyState`` is ``complete``."""
        return WebDriverWait(self.current_webdriver, timeout).until(
            lambda driver: driver.execute_script("return document.readyState") == "complete"
        )

    # ----- raw selectors -------------------------------------------------

    @recorded
    def find_element_by(self, selector: str, by: str = "css selector") -> Any:
        """Find by a raw selector (no saved ``TestObject``) and make it the current element."""
        element = self.current_webdriver.find_element(resolve_by(by), selector)
        web_element_wrapper.current_web_element = element
        return element

    @recorded
    def find_elements_by(self, selector: str, by: str = "css selector") -> list[Any]:
        """Find every match of a raw selector; they become the current element list."""
        elements = self.current_webdriver.find_elements(resolve_by(by), selector)
        web_element_wrapper.current_web_element_list = elements
        return elements

    # ----- JavaScript dialogs --------------------------------------------

    @recorded
    def alert_accept(self, prompt_text: str | None = None) -> None:
        """Accept the open alert / confirm / prompt, typing ``prompt_text`` into a prompt first."""
        alert = self.current_webdriver.switch_to.alert
        if prompt_text is not None:
            alert.send_keys(prompt_text)
        alert.accept()

    @recorded
    def alert_dismiss(self) -> None:
        """Dismiss the open alert / confirm / prompt."""
        self.current_webdriver.switch_to.alert.dismiss()

    @recorded
    def alert_text(self) -> str:
        """The message of the open dialog."""
        return self.current_webdriver.switch_to.alert.text

    # ----- emulation, permissions, clock (Chromium DevTools) ----------------

    @recorded
    def emulate_device(self, name: str) -> None:
        """
        套用具名裝置（``utils/device_emulation`` 預設）
        Emulate a named device preset: viewport, scale, touch and user agent
        (Chromium only, through CDP).
        """
        preset = get_preset(name)
        self.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", cdp_emulation_command(name))
        self.execute_cdp_cmd("Emulation.setUserAgentOverride", {"userAgent": preset.user_agent})
        self.execute_cdp_cmd("Emulation.setTouchEmulationEnabled", {"enabled": preset.has_touch})

    @staticmethod
    def list_devices() -> list[str]:
        """The device preset names :meth:`emulate_device` accepts."""
        return available_presets()

    @recorded
    def grant_permissions(self, permissions: list[str], origin: str | None = None) -> None:
        """
        授予瀏覽器權限（Chromium，CDP）
        Grant permissions, by Playwright name (``geolocation``, ``notifications``,
        ``camera``, ``clipboard-read`` …) or Chrome DevTools name, for ``origin`` or
        every origin.
        """
        params: dict[str, Any] = {"permissions": sorted({_PERMISSIONS.get(p, p) for p in permissions})}
        if origin:
            params["origin"] = origin
        self.execute_cdp_cmd("Browser.grantPermissions", params)

    @recorded
    def clear_permissions(self) -> None:
        """Reset every granted permission."""
        self.execute_cdp_cmd("Browser.resetPermissions", {})

    @recorded
    def clock_freeze(self, moment: str | int | float, advance_ms_per_real_second: float = 0.0) -> None:
        """
        凍結頁面時間
        Make ``Date``, ``Date.now()`` and ``performance.now()`` report ``moment`` (ISO
        text or epoch milliseconds) in the current page and every page loaded after it;
        ``advance_ms_per_real_second`` lets the frozen clock run slowly.
        """
        script = build_freezer_script(freeze_at(moment, advance_ms_per_real_second=advance_ms_per_real_second))
        self.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": script})
        self.current_webdriver.execute_script(script)
