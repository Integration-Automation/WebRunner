"""
非同步執行引擎 / Run action lists with asyncio: several at once, each its own browser context.

:class:`AsyncExecutor` runs an action list in order, like ``execute_action``:

* ``WR_apw_*`` commands (:mod:`~je_web_runner.utils.async_executor.commands`) are awaited
  in the list's own :class:`~je_web_runner.utils.async_executor.session.AsyncSession`,
  opened on first use: a fresh browser context, so concurrent lists are separate users
  with their own cookies, storage and tabs, sharing one browser;
* every other command of the synchronous executor (``WR_*``, the safe builtins) runs in a
  worker thread through ``asyncio.to_thread``, so a blocking call does not stall the other
  lists. Those commands share the process-wide singletons (the Selenium driver, the
  Playwright wrapper), exactly as ``--parallel-mode thread`` does; only ``WR_apw_*`` state
  is per list.

The synchronous executor's gates apply to both: commands it refuses (``restricted``) and
the arbitrary-script gate (``WR_apw_evaluate`` included). :meth:`AsyncExecutor.run_many`
runs lists concurrently with ``asyncio.gather``, at most ``concurrency`` at a time.
"""
from __future__ import annotations

import asyncio
from typing import Any, Sequence

from je_web_runner.utils.async_executor.commands import ARBITRARY_SCRIPT_COMMANDS, ASYNC_COMMANDS
from je_web_runner.utils.async_executor.session import AsyncBrowserPool, AsyncSession
from je_web_runner.utils.exception.exceptions import WebRunnerExecuteException, describe_error
from je_web_runner.utils.executor.action_executor import Executor, executor as sync_executor
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.utils.test_record.test_record_class import record_action_to_list


class _RecordedFailure(WebRunnerExecuteException):
    """A sync command's failure, already worded by ``Executor.execute_one`` (artifacts included)."""


def _arguments(action: list) -> tuple[list, dict]:
    """``(args, kwargs)`` of ``["WR_x"]`` / ``["WR_x", {...}]`` / ``["WR_x", [...]]`` / ``["WR_x", [...], {...}]``."""
    if len(action) == 1:
        return [], {}
    if len(action) == 2:
        return ([], dict(action[1])) if isinstance(action[1], dict) else (list(action[1]), {})
    if len(action) == 3 and isinstance(action[1], (list, tuple)) and isinstance(action[2], dict):
        return list(action[1]), dict(action[2])
    raise WebRunnerExecuteException(f"malformed action {action!r}")


class AsyncExecutor:
    """Runs action lists with asyncio; ``WR_apw_*`` state is per list, everything else is the sync executor's."""

    def __init__(self, browser: str = "chromium", headless: bool = True, sync: Executor | None = None,
                 **launch_options: Any) -> None:
        self.sync = sync or sync_executor
        self.pool = AsyncBrowserPool(browser, headless, **launch_options)

    async def _run_action(self, action: list, state: dict[str, Any], context_options: dict[str, Any]) -> Any:
        if not isinstance(action, list) or not action or not isinstance(action[0], str):
            raise WebRunnerExecuteException(f"an action is a list that starts with a command name, got {action!r}")
        name = action[0]
        args, kwargs = _arguments(action)
        command = ASYNC_COMMANDS.get(name)
        if command is None:
            # The sync executor applies its gates, retry policy and failure screenshots; its
            # error message is already the failure text the record shows.
            try:
                return await asyncio.to_thread(self.sync.execute_one, action)
            except WebRunnerExecuteException as error:
                raise _RecordedFailure(str(error)) from error
        self.sync.check_allowed(name, ARBITRARY_SCRIPT_COMMANDS)
        if state.get("session") is None:
            state["session"] = await self.pool.open_session(**context_options)
        try:
            result = await command(state["session"], *args, **kwargs)
        except Exception as error:
            record_action_to_list(name, kwargs or {"args": args}, error)
            raise
        record_action_to_list(name, kwargs or {"args": args}, None)
        return result

    async def run(self, action_list: list | dict, context_options: dict[str, Any] | None = None
                  ) -> tuple[dict[str, Any], list[str]]:
        """
        依序執行一份動作清單
        Run one action list in order and return ``(record, failed)`` as
        ``Executor.collect_action_results`` does: a failed action is recorded and the next
        one runs. The list's browser context is closed at the end.
        """
        actions = Executor.action_list_of(action_list)
        record: dict[str, Any] = {}
        failed: list[str] = []
        state: dict[str, AsyncSession | None] = {"session": None}
        try:
            for action in actions:
                key = "execute: " + str(action)
                try:
                    record[key] = await self._run_action(action, state, context_options or {})
                except Exception as error:  # every action's own failure is recorded, not raised
                    web_runner_logger.error(f"async execute_action, action: {action}, failed: {error!r}")
                    record[key] = str(error) if isinstance(error, _RecordedFailure) else describe_error(error)
                    failed.append(key)
        finally:
            if state["session"] is not None:
                await state["session"].close()
        return record, failed

    async def run_many(self, action_lists: Sequence[list | dict], concurrency: int = 4,
                       context_options: dict[str, Any] | None = None) -> list[tuple[dict[str, Any], list[str]]]:
        """
        同時執行多份動作清單
        Run ``action_lists`` concurrently, at most ``concurrency`` at a time, each in its own
        browser context; returns their ``(record, failed)`` in the input order.
        """
        if int(concurrency) < 1:
            raise WebRunnerExecuteException("concurrency must be at least 1")
        gate = asyncio.Semaphore(int(concurrency))

        async def one(action_list: list | dict) -> tuple[dict[str, Any], list[str]]:
            async with gate:
                return await self.run(action_list, context_options)
        return list(await asyncio.gather(*(one(action_list) for action_list in action_lists)))

    async def close(self) -> None:
        """Close the shared browser."""
        await self.pool.close()

    async def __aenter__(self) -> AsyncExecutor:
        return self

    async def __aexit__(self, *_exc: Any) -> None:
        await self.close()


async def async_execute_action(action_list: list | dict, browser: str = "chromium", headless: bool = True
                               ) -> tuple[dict[str, Any], list[str]]:
    """Run one action list with a temporary :class:`AsyncExecutor`; returns ``(record, failed)``."""
    async with AsyncExecutor(browser, headless) as runner:
        return await runner.run(action_list)


async def async_execute_many(action_lists: Sequence[list | dict], concurrency: int = 4, browser: str = "chromium",
                             headless: bool = True) -> list[tuple[dict[str, Any], list[str]]]:
    """Run several action lists concurrently in one browser, one context each."""
    async with AsyncExecutor(browser, headless) as runner:
        return await runner.run_many(action_lists, concurrency)


def run_action_lists(action_lists: Sequence[list | dict], concurrency: int = 4, browser: str = "chromium",
                     headless: bool = True) -> list[tuple[dict[str, Any], list[str]]]:
    """
    從同步程式碼執行（自行開啟事件迴圈）
    :func:`async_execute_many` for synchronous callers (the CLI): runs its own event loop,
    so it cannot be called from inside a running one.
    """
    return asyncio.run(async_execute_many(action_lists, concurrency, browser, headless))
