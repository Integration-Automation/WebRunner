"""Auto-dismiss helpers for common GDPR / cookie consent banners."""
from je_web_runner.utils.cookie_consent.consent import (
    ConsentBannerError,
    ConsentDismisser,
    common_dismiss_selectors,
    register_selector,
)

__all__ = [
    "ConsentBannerError",
    "ConsentDismisser",
    "common_dismiss_selectors",
    "register_selector",
]
