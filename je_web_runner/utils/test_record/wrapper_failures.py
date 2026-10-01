"""
Selenium wrapper 失敗的處理策略 / What a failed Selenium wrapper call does to its action.

The Selenium wrapper methods (``WebDriverWrapper``, ``WebElementWrapper``,
``WebdriverManager``) have always caught every exception, recorded it in the test record
and returned, so ``execute_action`` reported the step as passed: a wrong
``WR_element_assert`` or a ``WR_to_url`` that never loaded passed. Their Playwright twins
raise. Each wrapper's ``except`` block now ends in :func:`settle_wrapper_failure`:

* ``None`` (the default, deprecated): the call still returns, with a
  ``DeprecationWarning`` and a WARNING in the log (once per method), because a future
  release will raise (README › Public API & Deprecation Policy);
* ``True``: the error is raised after it is recorded, so the action fails;
* ``False``: the call returns silently, the old behaviour, chosen explicitly.
"""
from __future__ import annotations

import warnings

from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class _WrapperFailurePolicy:
    """Process-wide switch; the Selenium wrappers are module-level singletons too."""

    def __init__(self) -> None:
        self.raise_errors: bool | None = None
        self.warned: set[str] = set()


wrapper_failure_policy = _WrapperFailurePolicy()


def set_raise_wrapper_errors(enabled: bool | None) -> None:
    """
    設定 Selenium wrapper 失敗時是否讓動作失敗
    ``True``: a failed Selenium wrapper call raises after recording, so its action fails.
    ``False``: it returns as it always did, without the deprecation warning. ``None``:
    the deprecated default (returns, and warns).
    """
    wrapper_failure_policy.raise_errors = None if enabled is None else bool(enabled)


def settle_wrapper_failure(error: Exception, where: str) -> None:
    """
    在 wrapper 記錄失敗之後呼叫：嚴格模式時拋出，預設時發出棄用警告
    Call at the end of a Selenium wrapper's ``except`` block, after the failure is
    recorded. Raises ``error`` when :func:`set_raise_wrapper_errors` is True; warns once
    per ``where`` when it was never set; does nothing when it is False.
    """
    if wrapper_failure_policy.raise_errors is True:
        raise error
    if wrapper_failure_policy.raise_errors is False or where in wrapper_failure_policy.warned:
        return
    wrapper_failure_policy.warned.add(where)
    message = (
        f"{where} failed ({error!r}) and its action still passes; a future release will fail the action. "
        "Call executor.set_raise_wrapper_errors(True), or put [\"WR_set_raise_wrapper_errors\", [true]] "
        "first in the action file, to get that now; set it False to keep the old behaviour."
    )
    web_runner_logger.warning(message)
    warnings.warn(message, DeprecationWarning, stacklevel=3)
