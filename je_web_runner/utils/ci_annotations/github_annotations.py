"""
GitHub Actions 行內註解產生器：把失敗轉成 ``::error::`` 訊息。
GitHub Actions inline-annotation emitter. Failures become ``::error file=…``
lines that GitHub renders inline on the PR diff.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import IO, Iterable, List, Optional

# defusedxml-protected XML reader; CLAUDE.md requires this for parsing.
from defusedxml import ElementTree as DefusedET

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.utils.test_record.test_record_class import test_record_instance


class AnnotationError(WebRunnerException):
    """Raised when annotations cannot be produced."""


_NO_EXCEPTION = "None"


def _escape(message: str) -> str:
    """Escape for the workflow-command syntax: %, \\r, and \\n must be encoded."""
    return (
        message.replace("%", "%25")
        .replace("\r", "%0D")
        .replace("\n", "%0A")
    )


def format_error_annotation(
    message: str,
    file: Optional[str] = None,
    line: Optional[int] = None,
    col: Optional[int] = None,
    title: Optional[str] = None,
) -> str:
    """
    產出 ``::error file=...::message`` 行
    Format a single ``::error …::message`` workflow command line.
    """
    parts: List[str] = []
    if file:
        parts.append(f"file={file}")
    if line is not None:
        parts.append(f"line={int(line)}")
    if col is not None:
        parts.append(f"col={int(col)}")
    if title:
        parts.append(f"title={_escape(title)}")
    suffix = (" " + ",".join(parts)) if parts else ""
    return f"::error{suffix}::{_escape(message)}"


def emit_failure_annotations(
    stream: Optional[IO[str]] = None,
    file: Optional[str] = None,
) -> List[str]:
    """
    對 ``test_record_instance`` 內每個失敗紀錄輸出一行 annotation
    Emit one annotation per failure in ``test_record_instance``.

    :param stream: 輸出串流；預設 ``sys.stdout`` (GitHub Actions 讀的位置)
    :param file: 全部 annotations 套用的檔案路徑（可選）
    :return: 寫出的字串清單
    """
    web_runner_logger.info("emit_failure_annotations")
    out_stream = stream if stream is not None else sys.stdout
    lines: List[str] = []
    for record in test_record_instance.test_record_list:
        if record.get("program_exception", _NO_EXCEPTION) == _NO_EXCEPTION:
            continue
        line = format_error_annotation(
            message=str(record.get("program_exception")),
            file=file,
            title=str(record.get("function_name")),
        )
        lines.append(line)
        out_stream.write(line + "\n")
    return lines


def emit_from_junit_xml(
    junit_path: str,
    stream: Optional[IO[str]] = None,
) -> List[str]:
    """
    讀取 JUnit XML 並對其中每個 ``<failure>`` 輸出一行 annotation
    Parse a JUnit XML report and emit ``::error::`` annotations for each
    ``<failure>`` element.
    """
    target = Path(junit_path)
    if not target.exists():
        raise AnnotationError(f"junit XML not found: {junit_path}")
    out_stream = stream if stream is not None else sys.stdout
    try:
        tree = DefusedET.parse(str(target))
    except DefusedET.ParseError as error:
        raise AnnotationError(f"failed to parse JUnit XML: {error}") from error
    root = tree.getroot()
    lines: List[str] = []
    for testcase in _iter_testcases(root):
        failure = testcase.find("failure")
        if failure is None:
            continue
        message = failure.get("message") or (failure.text or "").strip() or "test failed"
        title = testcase.get("name") or testcase.get("classname")
        line = format_error_annotation(message=message, title=title)
        lines.append(line)
        out_stream.write(line + "\n")
    return lines


def _iter_testcases(root) -> Iterable:
    """Yield ``<testcase>`` elements regardless of suite nesting."""
    if root.tag == "testcase":
        yield root
        return
    for testcase in root.iter("testcase"):
        yield testcase
