"""儀表板設定與錯誤 / Dashboard configuration and error type."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from je_web_runner.utils.exception.exceptions import WebRunnerException


class LiveDashboardError(WebRunnerException):
    """Raised on configuration / startup failures."""


@dataclass
class DashboardConfig:
    """
    指定每個資料來源檔案路徑。任何一個 None 就會在 UI 上顯示成空白。
    """
    ledger_path: str | Path | None = None
    quarantine_path: str | Path | None = None
    locator_findings_path: str | Path | None = None
    schedule_path: str | Path | None = None
    triage_report_path: str | Path | None = None
    bind_host: str = "127.0.0.1"
    bind_port: int = 0

    def __post_init__(self) -> None:
        for attr in (
            "ledger_path", "quarantine_path", "locator_findings_path",
            "schedule_path", "triage_report_path",
        ):
            value = getattr(self, attr)
            if value is not None and not isinstance(value, Path):
                setattr(self, attr, Path(value))
