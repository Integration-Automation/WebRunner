"""Per-request header tampering for security testing."""
from je_web_runner.utils.header_tampering.tamper import (
    HeaderRule,
    HeaderTamperingError,
    HeaderTampering,
)

__all__ = ["HeaderRule", "HeaderTampering", "HeaderTamperingError"]
