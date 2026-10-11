"""
把函式呼叫寫進測試紀錄的裝飾器 / A decorator that adds each call to the shared test record.
"""
from __future__ import annotations

import functools
import inspect
from typing import Any, Callable

from je_web_runner.utils.test_record.test_record_class import record_action_to_list


def recorded_calls(prefix: str, hidden: tuple[str, ...] = ()) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    把每次呼叫寫進測試紀錄（成功或失敗），例外照常往外丟
    Decorate a method so each call is added to the test record as ``<prefix> <method>``
    with its bound arguments, on success and on failure; the method's own exception
    still propagates, so the action fails. Arguments named in ``hidden`` are recorded as
    ``"<hidden>"`` (cookie values, headers).
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
                record_action_to_list(f"{prefix} {method.__name__}", params, error)
                raise
            record_action_to_list(f"{prefix} {method.__name__}", params, None)
            return result

        return wrapper

    return decorator
