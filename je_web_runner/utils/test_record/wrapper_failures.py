"""
Selenium wrapper 失敗的處理策略 / What a failed Selenium wrapper call does to its action.

The Selenium wrapper methods (``WebDriverWrapper``, ``WebElementWrapper``,
``WebdriverManager``) catch their exception, record it in the test record, and then end
their ``except`` block in :func:`settle_wrapper_failure`:

* ``True`` (the default): the error is raised after it is recorded, so the action fails,
  as the Playwright twins do;
* ``False``: the call returns and the action passes, the behaviour before the default
  changed; choose it explicitly with ``set_raise_wrapper_errors(False)``.
"""
from __future__ import annotations


class _WrapperFailurePolicy:
    """Process-wide switch; the Selenium wrappers are module-level singletons too."""

    def __init__(self) -> None:
        self.raise_errors: bool = True


wrapper_failure_policy = _WrapperFailurePolicy()


def set_raise_wrapper_errors(enabled: bool) -> None:
    """
    設定 Selenium wrapper 失敗時是否讓動作失敗
    ``True`` (the default): a failed Selenium wrapper call raises after recording, so its
    action fails. ``False``: it returns and the action passes.
    """
    wrapper_failure_policy.raise_errors = bool(enabled)


def settle_wrapper_failure(error: Exception) -> None:
    """
    在 wrapper 記錄失敗之後呼叫：預設拋出
    Call at the end of a Selenium wrapper's ``except`` block, after the failure is
    recorded: raises ``error`` unless :func:`set_raise_wrapper_errors` turned it off.
    """
    if wrapper_failure_policy.raise_errors:
        raise error
