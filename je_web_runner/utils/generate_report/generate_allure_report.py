"""
Allure 結果產生器：將 ``test_record_instance`` 轉成 Allure 相容的 JSON 結果檔。
Allure-compatible result generator: turn ``test_record_instance`` records
into ``<uuid>-result.json`` files that ``allure serve`` / ``allure
generate`` can consume.

備註 / Notes:
- 此模組只產生原始結果檔；HTML 報告由官方 ``allure`` CLI 產出。
  This module only writes the raw result JSON; the HTML report is rendered
  by the official ``allure`` CLI (``allure serve <dir>``).
"""
from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List

from je_web_runner.utils.exception.exception_tags import cant_generate_json_report
from je_web_runner.utils.exception.exceptions import WebRunnerGenerateJsonReportException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.utils.test_record.test_record_class import test_record_instance

_lock = Lock()
_NO_EXCEPTION_MARKER = "None"
_TIMESTAMP_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})(?:\.(\d+))?$")


def _parse_record_time(value: str) -> int:
    """Convert a record timestamp like '2026-04-25 12:34:56.789' to epoch-ms."""
    if not isinstance(value, str):
        return int(time.time() * 1000)
    match = _TIMESTAMP_RE.match(value.strip())
    if not match:
        return int(time.time() * 1000)
    try:
        timestamp = time.mktime(time.strptime(f"{match.group(1)} {match.group(2)}", "%Y-%m-%d %H:%M:%S"))
    except ValueError:
        return int(time.time() * 1000)
    micro = match.group(3) or "0"
    micro_seconds = int(micro.ljust(6, "0")[:6])
    return int(timestamp * 1000 + micro_seconds // 1000)


def _step_from_record(record: Dict[str, Any]) -> Dict[str, Any]:
    failed = record.get("program_exception", _NO_EXCEPTION_MARKER) != _NO_EXCEPTION_MARKER
    start = _parse_record_time(record.get("time", ""))
    return {
        "name": str(record.get("function_name", "unknown")),
        "status": "failed" if failed else "passed",
        "stage": "finished",
        "start": start,
        "stop": start,
        "parameters": [
            {"name": "local_param", "value": str(record.get("local_param"))}
        ],
        "statusDetails": (
            {"message": str(record.get("program_exception"))} if failed else {}
        ),
    }


def generate_allure() -> List[Dict[str, Any]]:
    """
    將目前的 record list 包成單一 Allure test case
    Wrap the current record list into a single Allure test case (with one
    step per recorded action).
    """
    web_runner_logger.info("generate_allure")
    records = test_record_instance.test_record_list
    if len(records) == 0:
        raise WebRunnerGenerateJsonReportException(cant_generate_json_report)

    steps = [_step_from_record(record) for record in records]
    overall_failed = any(step["status"] == "failed" for step in steps)
    start = steps[0]["start"] if steps else int(time.time() * 1000)
    stop = steps[-1]["stop"] if steps else start
    case = {
        "uuid": str(uuid.uuid4()),
        "name": "WebRunner action sequence",
        "fullName": "webrunner.action_sequence",
        "status": "failed" if overall_failed else "passed",
        "stage": "finished",
        "start": start,
        "stop": stop,
        "steps": steps,
        "labels": [
            {"name": "framework", "value": "webrunner"},
            {"name": "language", "value": "python"},
        ],
    }
    return [case]


def generate_allure_report(output_dir: str = "allure-results") -> List[str]:
    """
    把 test cases 寫成 ``<uuid>-result.json``
    Write the generated test cases as ``<uuid>-result.json`` files.

    :param output_dir: 輸出資料夾 / target directory
    :return: 寫出的檔案路徑清單 / list of file paths written
    """
    web_runner_logger.info(f"generate_allure_report: {output_dir}")
    cases = generate_allure()
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    written: List[str] = []
    for case in cases:
        out_path = target_dir / f"{case['uuid']}-result.json"
        try:
            _lock.acquire()
            with open(out_path, "w", encoding="utf-8") as out_file:
                json.dump(case, out_file, indent=2)
            written.append(str(out_path))
        except OSError as error:
            web_runner_logger.error(f"generate_allure_report write failed: {error!r}")
        finally:
            _lock.release()
    return written
