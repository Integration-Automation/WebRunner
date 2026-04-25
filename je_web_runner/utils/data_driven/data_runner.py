"""
資料驅動測試：以 CSV / JSON 表格逐列展開 ``${ROW.col}`` 占位符並執行 action。
Data-driven testing helper: read CSV / JSON datasets and iterate the same
action JSON once per row, expanding ``${ROW.column_name}`` placeholders.
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, List

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class DataDrivenError(WebRunnerException):
    """Raised when a dataset cannot be loaded or a placeholder is unknown."""


_ROW_PLACEHOLDER_RE = re.compile(r"\$\{ROW\.([A-Za-z_][A-Za-z0-9_]*)\}")


def load_dataset_csv(path: str, encoding: str = "utf-8") -> List[Dict[str, str]]:
    """
    讀取 CSV 為 list of dict（首列為欄位名）
    Read a CSV file into a list of dicts using the first row as headers.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise DataDrivenError(f"dataset not found: {path}")
    web_runner_logger.info(f"load_dataset_csv: {path}")
    with open(file_path, encoding=encoding, newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        return [dict(row) for row in reader]


def load_dataset_json(path: str, encoding: str = "utf-8") -> List[Dict[str, Any]]:
    """
    讀取 JSON 為 list of dict
    Read a JSON file into a list of dicts.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise DataDrivenError(f"dataset not found: {path}")
    web_runner_logger.info(f"load_dataset_json: {path}")
    with open(file_path, encoding=encoding) as json_file:
        data = json.load(json_file)
    if not isinstance(data, list):
        raise DataDrivenError(f"dataset JSON must be a list of objects, got {type(data).__name__}")
    return data


def _expand_string(text: str, row: Dict[str, Any]) -> str:
    def _resolve(match: re.Match) -> str:
        column = match.group(1)
        if column not in row:
            raise DataDrivenError(f"unknown column in placeholder: ${{ROW.{column}}}")
        return str(row[column])

    return _ROW_PLACEHOLDER_RE.sub(_resolve, text)


def expand_with_row(data: Any, row: Dict[str, Any]) -> Any:
    """
    遞迴展開 ``${ROW.col}`` 占位符
    Recursively expand ``${ROW.col}`` placeholders against a row mapping.
    """
    if isinstance(data, str):
        return _expand_string(data, row)
    if isinstance(data, dict):
        return {key: expand_with_row(value, row) for key, value in data.items()}
    if isinstance(data, list):
        return [expand_with_row(item, row) for item in data]
    if isinstance(data, tuple):
        return tuple(expand_with_row(item, row) for item in data)
    return data


def run_with_dataset(
    action_data: Any,
    rows: List[Dict[str, Any]],
    runner: Callable[[Any], Any],
) -> List[Any]:
    """
    對每筆 row 展開 placeholders 後呼叫 ``runner``
    For each row, expand placeholders against ``action_data`` and call
    ``runner`` on the materialised actions.

    :param action_data: 含 ``${ROW.col}`` 的 action 結構
    :param rows: 來自 dataset 的 row dicts
    :param runner: 通常是 ``execute_action`` / ``execute_files``
    :return: 每列執行結果組成的 list
    """
    results = []
    for index, row in enumerate(rows):
        web_runner_logger.info(f"run_with_dataset row #{index}")
        materialised = expand_with_row(action_data, row)
        results.append(runner(materialised))
    return results
