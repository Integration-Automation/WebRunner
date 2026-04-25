"""
Factory 樣板：可組合的測試 entity 產生器（user / order / product）。
Composable test-data factories. ``Factory(defaults)`` lazily evaluates any
callable defaults so each ``build()`` produces a fresh instance, suitable
for setup blocks in action JSON.
"""
from __future__ import annotations

import itertools
import time
from typing import Any, Callable, Dict, List

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class FactoryError(WebRunnerException):
    """Raised when a factory cannot evaluate its defaults."""


class Factory:
    """
    用 ``defaults`` (常數或無參 callable) 組合 dict
    Build dicts whose values come from a defaults map. Callable values are
    invoked for every ``build()`` so faker-style providers stay fresh.
    """

    def __init__(self, defaults: Dict[str, Any]):
        if not isinstance(defaults, dict):
            raise FactoryError("Factory defaults must be a dict")
        self._defaults: Dict[str, Any] = dict(defaults)

    def build(self, **overrides: Any) -> Dict[str, Any]:
        web_runner_logger.info("Factory.build")
        out: Dict[str, Any] = {}
        for key, value in self._defaults.items():
            out[key] = value() if callable(value) else value
        out.update(overrides)
        return out

    def build_batch(self, count: int, **overrides: Any) -> List[Dict[str, Any]]:
        return [self.build(**overrides) for _ in range(int(count))]

    def extend(self, **extra_defaults: Any) -> "Factory":
        """Return a new Factory with additional / overriding defaults."""
        merged = {**self._defaults, **extra_defaults}
        return Factory(merged)


def _counter():
    """Deterministic incrementing id source."""
    counter = itertools.count(1)

    def _next() -> int:
        return next(counter)

    return _next


def _faker_safe(method: str, fallback: Callable[[], Any]) -> Callable[[], Any]:
    """Return a callable that uses faker if available, otherwise ``fallback``."""
    def _value():
        try:
            from je_web_runner.utils.test_data.faker_integration import fake_value
            return fake_value(method)
        except Exception:  # noqa: BLE001 — faker not installed or provider missing
            return fallback()
    return _value


def user_factory(prefix: str = "user") -> Factory:
    """Default user shape: id / name / email / password."""
    counter = _counter()
    return Factory({
        "id": counter,
        "name": _faker_safe("name", lambda: f"{prefix}-name"),
        "email": _faker_safe("email", lambda: f"{prefix}-{int(time.time() * 1000)}@example.com"),
        "password": _faker_safe("password", lambda: "Hunter2!Hunter2!"),
    })


def order_factory(default_currency: str = "USD") -> Factory:
    counter = _counter()
    return Factory({
        "id": counter,
        "amount": lambda: 100,
        "currency": default_currency,
        "status": "pending",
    })


def product_factory() -> Factory:
    counter = _counter()
    return Factory({
        "id": counter,
        "name": _faker_safe("word", lambda: "widget"),
        "price": lambda: 19.99,
        "in_stock": True,
    })
