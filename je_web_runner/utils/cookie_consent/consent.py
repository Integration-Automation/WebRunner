"""
GDPR / Cookie 同意彈窗自動處理：依預設 selector 庫嘗試點擊「Accept All」按鈕。
Auto-dismiss for cookie / GDPR consent banners. Tries each registered
selector in order, clicks the first match, and reports which one fired so
test traces stay diagnosable.

The default selector list covers OneTrust, TrustArc, Cookiebot, Quantcast,
Didomi, GoogleFundingChoices, plus common per-region fallbacks.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class ConsentBannerError(WebRunnerException):
    """Raised when consent dismissal fails or driver is unsupported."""


_DEFAULT_SELECTORS: List[str] = [
    "#onetrust-accept-btn-handler",
    "#truste-consent-button",
    "#CybotCookiebotDialogBodyLevelButtonAccept",
    "#qc-cmp2-ui button[mode='primary']",
    "#didomi-notice-agree-button",
    "button[aria-label='Consent']",
    "button[aria-label*='Accept all']",
    "button[aria-label*='I agree']",
    "button[data-testid='cookie-accept-all']",
    "button.fc-cta-consent",  # GoogleFundingChoices
    ".cookie-consent-accept",
    "[id*='accept-cookies']",
    "[class*='accept-cookies']",
]


@dataclass
class ConsentDismisser:
    """Try each selector against a driver / page; click the first hit."""

    selectors: List[str] = field(default_factory=lambda: list(_DEFAULT_SELECTORS))

    def add_selector(self, selector: str) -> None:
        if not selector or selector in self.selectors:
            return
        self.selectors.append(selector)

    def dismiss(self, driver: Any, timeout_per_selector: float = 0.5) -> Optional[str]:
        """
        嘗試點擊 banner 上的 Accept 按鈕；找不到時回傳 None
        Click the first matching consent button. Returns the selector that
        was clicked, or ``None`` if no banner was found.
        """
        for selector in self.selectors:
            if self._try_selector(driver, selector, timeout_per_selector):
                web_runner_logger.info(f"consent dismissed via {selector!r}")
                return selector
        return None

    def _try_selector(self, driver: Any, selector: str, timeout: float) -> bool:
        try:
            if hasattr(driver, "execute_script"):
                # Selenium path
                clicked = driver.execute_script(
                    "const el = document.querySelector(arguments[0]);"
                    "if (el) { el.click(); return true; }"
                    "return false;",
                    selector,
                )
                return bool(clicked)
            if hasattr(driver, "click") and hasattr(driver, "wait_for_selector"):
                # Playwright page
                element = driver.wait_for_selector(
                    selector, state="visible", timeout=int(timeout * 1000)
                )
                if element is not None:
                    element.click()
                    return True
                return False
            raise ConsentBannerError("driver type not supported")
        except ConsentBannerError:
            raise
        except Exception as error:  # pylint: disable=broad-except
            web_runner_logger.debug(
                f"consent selector {selector!r} miss: {error!r}"
            )
            return False


def common_dismiss_selectors() -> List[str]:
    return list(_DEFAULT_SELECTORS)


def register_selector(selector: str) -> None:
    """Append ``selector`` to the module-default list (idempotent)."""
    if not selector:
        raise ConsentBannerError("selector must be non-empty")
    if selector not in _DEFAULT_SELECTORS:
        _DEFAULT_SELECTORS.append(selector)
