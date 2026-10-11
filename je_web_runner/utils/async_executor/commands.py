"""
非同步 Playwright 命令 / The ``WR_apw_*`` commands: async Playwright, one context per action list.

Each takes the action list's :class:`~je_web_runner.utils.async_executor.session.AsyncSession`
first; :class:`~je_web_runner.utils.async_executor.executor.AsyncExecutor` passes it, so an
action reads ``["WR_apw_click", {"selector": "#buy"}]``. They exist only in the async
executor's command table. Assertions raise ``AsyncCommandError``.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

from je_web_runner.utils.async_executor.session import AsyncSession
from je_web_runner.utils.exception.exceptions import WebRunnerException


class AsyncCommandError(WebRunnerException):
    """An async assertion failed or a wait ran out."""


async def goto(session: AsyncSession, url: str, wait_until: str = "load") -> str:
    """Navigate the current page (opening one first if none is open); returns the final URL."""
    page = session.page if session.pages else await session.new_page()
    await page.goto(url, wait_until=wait_until)
    return page.url


async def new_page(session: AsyncSession, url: str | None = None) -> int:
    """Open a page (another tab of the same user), make it current, optionally load ``url``; returns its index."""
    page = await session.new_page()
    if url:
        await page.goto(url)
    return session.current


async def switch_to_page(session: AsyncSession, index: int) -> str:
    """Make page ``index`` current; returns its URL."""
    return session.switch_to(index).url


async def close_page(session: AsyncSession) -> int:
    """Close the current page; returns how many stay open."""
    await session.close_page()
    return len(session.pages)


async def click(session: AsyncSession, selector: str) -> None:
    """Click the element ``selector`` matches (Playwright waits until it is actionable)."""
    await session.page.click(selector)


async def fill(session: AsyncSession, selector: str, value: str) -> None:
    """Fill an input."""
    await session.page.fill(selector, value)


async def press(session: AsyncSession, selector: str, key: str) -> None:
    """Press ``key`` (``Enter``, ``Control+A`` …) in the element."""
    await session.page.press(selector, key)


async def text(session: AsyncSession, selector: str) -> str:
    """The element's inner text."""
    return await session.page.inner_text(selector)


async def title(session: AsyncSession) -> str:
    """The current page's title."""
    return await session.page.title()


async def url(session: AsyncSession) -> str:
    """The current page's URL."""
    return session.page.url


async def wait_for_selector(session: AsyncSession, selector: str, state: str = "visible",
                            timeout: float = 10.0) -> None:
    """Wait until ``selector`` is ``attached`` / ``detached`` / ``visible`` / ``hidden`` (``timeout`` in seconds)."""
    await session.page.wait_for_selector(selector, state=state, timeout=float(timeout) * 1000)


async def assert_text(session: AsyncSession, selector: str, expected: str) -> str:
    """Fail unless the element's text contains ``expected``; returns the text."""
    actual = await session.page.inner_text(selector)
    if expected not in actual:
        raise AsyncCommandError(f"text of {selector!r} is {actual!r}, expected it to contain {expected!r}")
    return actual


async def assert_title(session: AsyncSession, expected: str) -> str:
    """Fail unless the page title contains ``expected``; returns the title."""
    actual = await session.page.title()
    if expected not in actual:
        raise AsyncCommandError(f"title is {actual!r}, expected it to contain {expected!r}")
    return actual


async def evaluate(session: AsyncSession, script: str, arg: Any = None) -> Any:
    """Evaluate JavaScript in the page (behind the arbitrary-script gate)."""
    return await session.page.evaluate(script, arg)


async def screenshot(session: AsyncSession, path: str, full_page: bool = False) -> str:
    """Save a PNG of the current page; returns the path."""
    await session.page.screenshot(path=path, full_page=full_page)
    return path


async def sleep(session: AsyncSession, seconds: float) -> None:  # the session is unused: every command takes it
    """Pause this action list only; the others keep running."""
    await asyncio.sleep(float(seconds))


async def websocket_messages(session: AsyncSession, direction: str | None = None) -> list[dict[str, Any]]:
    """Every WebSocket frame the session's pages sent or received: ``{url, direction, payload}``."""
    return [frame for frame in session.websocket_frames if direction is None or frame["direction"] == direction]


async def wait_for_websocket_message(session: AsyncSession, contains: str, timeout: float = 10.0) -> dict[str, Any]:
    """Wait until a received WebSocket frame contains ``contains``; returns it."""
    deadline = time.monotonic() + float(timeout)
    while True:
        for frame in session.websocket_frames:
            if frame["direction"] == "received" and contains in str(frame["payload"]):
                return frame
        if time.monotonic() >= deadline:
            raise AsyncCommandError(f"no WebSocket message containing {contains!r} within {timeout}s")
        await asyncio.sleep(0.05)


ASYNC_COMMANDS = {
    "WR_apw_goto": goto,
    "WR_apw_new_page": new_page,
    "WR_apw_switch_to_page": switch_to_page,
    "WR_apw_close_page": close_page,
    "WR_apw_click": click,
    "WR_apw_fill": fill,
    "WR_apw_press": press,
    "WR_apw_text": text,
    "WR_apw_title": title,
    "WR_apw_url": url,
    "WR_apw_wait_for_selector": wait_for_selector,
    "WR_apw_assert_text": assert_text,
    "WR_apw_assert_title": assert_title,
    "WR_apw_evaluate": evaluate,
    "WR_apw_screenshot": screenshot,
    "WR_apw_sleep": sleep,
    "WR_apw_websocket_messages": websocket_messages,
    "WR_apw_wait_for_websocket_message": wait_for_websocket_message,
}
# Commands that ship a script string to the browser: refused when the arbitrary-script gate is closed.
ARBITRARY_SCRIPT_COMMANDS = frozenset({"WR_apw_evaluate"})
