"""
CDP performance tracing 包裝：在 Chromium 系瀏覽器上錄製效能追蹤，
存成可載入 Chrome DevTools 「Performance」面板的 JSON 檔。
CDP performance tracing helper: record a perf trace on Chromium-family
browsers and save the JSON for loading into Chrome DevTools "Performance".

為何要走獨立 WebSocket / Why a dedicated WebSocket
------------------------------------------------
``Tracing.start`` 與 ``Tracing.dataCollected`` / ``Tracing.tracingComplete``
事件必須在同一個 CDP target session 才能配對。Selenium 的
``execute_cdp_cmd`` 走的是內部 session，事件不會傳出來；本模組改用
``CDPEventListener`` 在同一條 WebSocket 上送命令、收事件，確保完整收齊。
``Tracing.start`` and its corresponding ``Tracing.dataCollected`` /
``Tracing.tracingComplete`` events must share the same CDP target session.
Selenium's ``execute_cdp_cmd`` uses an internal session whose events never
reach user code; this module uses ``CDPEventListener`` so commands and
events live on the same WebSocket.
"""
from __future__ import annotations

import json
import threading
import time

from je_web_runner.utils.cdp.event_loop import CDPEventListener, CDPEventLoopError
from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class TracingError(WebRunnerException):
    """Raised when a CDP tracing session fails."""


def record_trace(
        driver,
        file_path: str,
        categories: list[str] | None = None,
        duration: float | None = None,
        completion_timeout: float = 30.0,
) -> str:
    """
    錄製一段 CDP performance trace 並存成 JSON 檔。
    Record a CDP performance trace session and save it as JSON.

    :param driver: Selenium WebDriver (Chromium 系)
    :param file_path: 輸出 JSON 路徑 / output JSON path
    :param categories: 要追蹤的 CDP categories；``None`` 表示使用 CDP 預設
                       Trace categories; ``None`` uses the CDP default set
    :param duration: 自動 sleep 多少秒再 ``Tracing.end``；``None`` 表示**等到使用者
                     另行呼叫 ``Tracing.end``**，但本函式僅做同步版本，``None``
                     會用 ``completion_timeout`` 等事件直接結束。
                     If set, sleep this many seconds before issuing ``Tracing.end``.
                     If ``None``, end immediately and rely on ``completion_timeout``.
    :param completion_timeout: 等 ``Tracing.tracingComplete`` 的最長秒數
                               Max seconds to wait for ``Tracing.tracingComplete``
    :return: 寫入的檔案路徑 / written file path
    """
    web_runner_logger.info(
        f"record_trace, file_path: {file_path}, categories: {categories}, "
        f"duration: {duration}"
    )
    events: list[dict] = []
    done = threading.Event()

    def _on_data(params: dict) -> None:
        events.extend(params.get("value") or [])

    def _on_complete(_params: dict) -> None:
        done.set()

    try:
        with CDPEventListener.from_driver(driver) as listener:
            listener.on("Tracing.dataCollected", _on_data)
            listener.on("Tracing.tracingComplete", _on_complete)

            start_params: dict = {"transferMode": "ReportEvents"}
            if categories:
                start_params["categories"] = ",".join(categories)
            listener.send("Tracing.start", start_params)

            if duration is not None and duration > 0:
                time.sleep(duration)

            listener.send("Tracing.end")
            if not done.wait(timeout=completion_timeout):
                raise TracingError(
                    f"Tracing.tracingComplete not received within {completion_timeout}s"
                )
    except CDPEventLoopError as error:
        raise TracingError(f"CDP event loop failed: {error!r}") from error

    with open(file_path, "w", encoding="utf-8") as fh:
        json.dump(events, fh, ensure_ascii=False)
    return file_path
