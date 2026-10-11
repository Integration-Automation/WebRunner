"""
非同步執行引擎 / Run action lists with asyncio, each in its own browser context (``WR_apw_*``).

The executor names load on first use: the synchronous command table imports
:mod:`~je_web_runner.utils.async_executor.commands`, and the executor imports that table.
"""
import importlib
from typing import TYPE_CHECKING, Any

from je_web_runner.utils.async_executor.commands import ASYNC_COMMANDS, AsyncCommandError
from je_web_runner.utils.async_executor.session import AsyncBrowserPool, AsyncSession, AsyncSessionError

_EXECUTOR_NAMES = ("AsyncExecutor", "async_execute_action", "async_execute_many", "run_action_lists")

if TYPE_CHECKING:
    from je_web_runner.utils.async_executor.executor import (
        AsyncExecutor, async_execute_action, async_execute_many, run_action_lists,
    )

# PEP 562 exports are provided by __getattr__ below, without a circular eager import.
__all__ = [
    "ASYNC_COMMANDS", "AsyncBrowserPool", "AsyncCommandError", "AsyncExecutor", "AsyncSession",
    "AsyncSessionError", "async_execute_action", "async_execute_many", "run_action_lists",
]


def __getattr__(name: str) -> Any:
    """Load the executor names on first use (PEP 562)."""
    if name in _EXECUTOR_NAMES:
        return getattr(importlib.import_module("je_web_runner.utils.async_executor.executor"), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
