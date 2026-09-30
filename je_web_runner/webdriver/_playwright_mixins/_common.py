"""Playwright backend 共用的例外、常數與報告紀錄 / Shared error, messages and record helper."""
from __future__ import annotations

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.test_record.test_record_class import record_action_to_list


class PlaywrightBackendError(WebRunnerException):
    """Raised when the Playwright backend is misused or unavailable."""


BROWSER_NOT_LAUNCHED = "Playwright browser not launched; call launch() first"
RUNTIME_NOT_STARTED = "Playwright runtime not started"
CLOCK_API_UNAVAILABLE = "Playwright clock API unavailable; upgrade Playwright"


def record(name: str, params, error: Exception | None) -> None:
    """Add a ``Playwright <name>`` entry to the shared test record."""
    record_action_to_list(f"Playwright {name}", params, error)
