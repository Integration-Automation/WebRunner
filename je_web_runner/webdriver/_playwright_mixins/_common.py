"""Playwright backend 共用的例外、常數與報告紀錄 / Shared error, messages and record helper."""
from __future__ import annotations

import functools
import inspect
from typing import Any, Callable

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


def recorded(hidden: tuple[str, ...] = ()) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    把每次呼叫寫進測試紀錄（成功或失敗），例外照常往外丟
    Decorate a page-level method so each call is added to the shared test record
    (``Playwright <method>``) with its bound arguments, on success and on failure.
    The method's own exception still propagates. Arguments named in ``hidden``
    are recorded as ``"<hidden>"`` (for example cookie values).
    """
    def decorator(method: Callable[..., Any]) -> Callable[..., Any]:
        signature = inspect.signature(method)

        @functools.wraps(method)
        def wrapper(self, *args: Any, **kwargs: Any) -> Any:
            params = dict(signature.bind(self, *args, **kwargs).arguments)
            params.pop("self", None)
            for name in hidden:
                if name in params:
                    params[name] = "<hidden>"
            try:
                result = method(self, *args, **kwargs)
            except Exception as error:
                record(method.__name__, params, error)
                raise
            record(method.__name__, params, None)
            return result

        return wrapper

    return decorator
