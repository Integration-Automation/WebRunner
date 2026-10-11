"""Playwright backend 共用的例外、常數與報告紀錄 / Shared error, messages and record helper."""
from __future__ import annotations

from typing import Any, Callable

from je_web_runner.utils.exception.exceptions import WebRunnerAssertException, WebRunnerException
from je_web_runner.utils.test_record.recorded import recorded_calls
from je_web_runner.utils.test_record.test_record_class import record_action_to_list


class PlaywrightBackendError(WebRunnerException):
    """Raised when the Playwright backend is misused or unavailable."""


BROWSER_NOT_LAUNCHED = "Playwright browser not launched; call launch() first"
RUNTIME_NOT_STARTED = "Playwright runtime not started"
CLOCK_API_UNAVAILABLE = "Playwright clock API unavailable; upgrade Playwright"


def record(name: str, params, error: Exception | None) -> None:
    """Add a ``Playwright <name>`` entry to the shared test record."""
    record_action_to_list(f"Playwright {name}", params, error)


def recorded(hidden: tuple[str, ...] = ()) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    把每次呼叫寫進測試紀錄（成功或失敗），例外照常往外丟
    Record each call of a page-level method as ``Playwright <method>``; see
    :func:`~je_web_runner.utils.test_record.recorded.recorded_calls`.
    """
    return recorded_calls("Playwright", hidden)


def check_fields(getters: dict[str, Callable[[], Any]], expected: dict[str, Any], what: str) -> None:
    """
    依 ``expected`` 斷言欄位值；只讀取被要求的欄位
    Assert each ``expected`` field against its getter, reading only the fields asked for.
    Raises :class:`WebRunnerAssertException` on the first mismatch or an unknown field.
    """
    for name, value in expected.items():
        getter = getters.get(name)
        if getter is None:
            raise WebRunnerAssertException(f"{what} has no field {name!r}; known: {sorted(getters)}")
        actual = getter()
        if actual != value:
            raise WebRunnerAssertException(f"{what} {name} should be {value!r} but was {actual!r}")
