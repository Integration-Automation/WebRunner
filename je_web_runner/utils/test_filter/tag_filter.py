"""
動作檔的標籤篩選：依 ``meta.tags`` 包含 / 排除執行檔。
Tag-based filtering for action files via an optional ``meta.tags`` key.

Action JSON 檔可選擇兩種頂層形狀：
- 既有：``[ ["WR_..."], ... ]``  或  ``{"webdriver_wrapper": [...]}``
- 加上 metadata：``{"webdriver_wrapper": [...], "meta": {"tags": ["smoke"]}}``
The action JSON file may now optionally include a ``meta`` block alongside
``webdriver_wrapper``.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class TagFilterError(WebRunnerException):
    """Raised when metadata cannot be read."""


def read_metadata(path: str) -> Dict[str, Any]:
    """
    讀取 action 檔的 ``meta`` 區塊；若檔案不是 dict 或沒有 meta，回傳空 dict
    Read the ``meta`` block from an action file (empty dict if absent).
    """
    file_path = Path(path)
    if not file_path.exists():
        raise TagFilterError(f"action file not found: {path}")
    try:
        with open(file_path, encoding="utf-8") as action_file:
            data = json.load(action_file)
    except ValueError as error:
        raise TagFilterError(f"action file not valid JSON: {path}") from error
    if not isinstance(data, dict):
        return {}
    meta = data.get("meta")
    return meta if isinstance(meta, dict) else {}


def _tag_set(meta: Dict[str, Any]) -> set:
    tags = meta.get("tags") or []
    return {str(tag) for tag in tags}


def match_tags(
    meta: Dict[str, Any],
    include: Optional[Sequence[str]] = None,
    exclude: Optional[Sequence[str]] = None,
) -> bool:
    """
    依 include / exclude 規則判斷檔案是否該執行
    Decide whether the file passes the tag filter.

    - ``include`` 非空：須至少符合一個（OR）
    - ``exclude`` 非空：不可符合任何一個（AND not）
    """
    tags = _tag_set(meta)
    include_set = {str(tag) for tag in (include or [])}
    exclude_set = {str(tag) for tag in (exclude or [])}
    if exclude_set and tags & exclude_set:
        return False
    if include_set and not tags & include_set:
        return False
    return True


def filter_paths(
    paths: Iterable[str],
    include: Optional[Sequence[str]] = None,
    exclude: Optional[Sequence[str]] = None,
) -> List[str]:
    """
    篩選 action 檔路徑清單
    Filter a list of action-file paths by their ``meta.tags``.
    Files without a ``meta`` block are kept only when ``include`` is empty.
    """
    web_runner_logger.info(
        f"filter_paths include={list(include or [])} exclude={list(exclude or [])}"
    )
    selected: List[str] = []
    for path in paths:
        try:
            meta = read_metadata(path)
        except TagFilterError:
            continue
        if match_tags(meta, include=include, exclude=exclude):
            selected.append(path)
    return selected
