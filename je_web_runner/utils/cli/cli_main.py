"""
WebRunner CLI 進入點，提供執行、驗證、平行、報告等子命令。
WebRunner CLI entry point: execute, validate, parallel, and report flags.
"""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Sequence

from je_web_runner.utils.exception.exception_tags import argparse_get_wrong_data
from je_web_runner.utils.exception.exceptions import WebRunnerExecuteException
from je_web_runner.utils.executor.action_executor import execute_action, execute_files
from je_web_runner.utils.file_process.get_dir_file_list import get_dir_files_as_list
from je_web_runner.utils.json.json_file.json_file import read_action_json
from je_web_runner.utils.json.json_validator import validate_action_file
from je_web_runner.utils.run_ledger.ledger import failed_files, record_run
from je_web_runner.utils.test_filter.tag_filter import filter_paths
from je_web_runner.utils.test_record.test_record_class import test_record_instance


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="webrunner")
    parser.add_argument("-e", "--execute_file", type=str, help="execute a single action JSON file")
    parser.add_argument("-d", "--execute_dir", type=str, help="execute all JSON files in a directory")
    parser.add_argument("--execute_str", type=str, help="execute a JSON action string directly")
    parser.add_argument("--validate", type=str, help="validate a single action JSON file (no execute)")
    parser.add_argument("--validate_dir", type=str, help="validate all JSON files in a directory (no execute)")
    parser.add_argument(
        "--parallel",
        type=int,
        default=1,
        help="when used with --execute_dir, run files concurrently (thread pool size)",
    )
    parser.add_argument(
        "--report",
        type=str,
        help="after execution, generate JSON / HTML / XML / JUnit reports with this base name",
    )
    parser.add_argument(
        "--tag",
        type=str,
        default=None,
        help="comma-separated tags; only run files whose meta.tags contains one",
    )
    parser.add_argument(
        "--exclude-tag",
        type=str,
        default=None,
        dest="exclude_tag",
        help="comma-separated tags; skip files whose meta.tags contains any",
    )
    parser.add_argument(
        "--ledger",
        type=str,
        default=None,
        help="path to a JSON ledger; pass/fail per file is appended after each run",
    )
    parser.add_argument(
        "--rerun-failed",
        type=str,
        default=None,
        dest="rerun_failed",
        help="path to a previously-written ledger; only files with a failed status are run",
    )
    return parser


def _split_csv(value: Optional[str]) -> list:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_execute_str(execute_str: str) -> list:
    """Parse a JSON string from CLI; tolerate Windows double-encoding from older shells."""
    if sys.platform in ("win32", "cygwin", "msys"):
        first = json.loads(execute_str)
        return json.loads(first) if isinstance(first, str) else first
    return json.loads(execute_str)


def _run_one_with_ledger(path: str, ledger_path: Optional[str]) -> None:
    """Run a single file; if a ledger path is given, record pass/fail."""
    failure_marker = "program_exception"
    failed = False
    if ledger_path:
        baseline = len(test_record_instance.test_record_list)
    try:
        execute_action(read_action_json(path))
    except Exception:  # noqa: BLE001 — we only want to log; executor itself rarely raises
        failed = True
        if not ledger_path:
            raise
    if ledger_path:
        new_records = test_record_instance.test_record_list[baseline:]
        if any(record.get(failure_marker, "None") != "None" for record in new_records):
            failed = True
        record_run(ledger_path, path, passed=not failed)


def _run_dir(
    directory: str,
    parallel: int,
    include_tags=None,
    exclude_tags=None,
    ledger_path: Optional[str] = None,
    rerun_only: Optional[Sequence[str]] = None,
) -> None:
    files = get_dir_files_as_list(directory)
    if rerun_only is not None:
        rerun_set = set(rerun_only)
        files = [path for path in files if path in rerun_set]
    if include_tags or exclude_tags:
        files = filter_paths(files, include=include_tags, exclude=exclude_tags)
    if parallel <= 1 and not ledger_path:
        execute_files(files)
        return
    if parallel <= 1:
        for path in files:
            _run_one_with_ledger(path, ledger_path)
        return
    with ThreadPoolExecutor(max_workers=parallel) as pool:
        list(pool.map(lambda path: _run_one_with_ledger(path, ledger_path), files))


def _generate_reports(base_name: str) -> None:
    # Imported lazily so the CLI does not pay the cost (or initialize globals)
    # for users who never request a report.
    from je_web_runner.utils.generate_report.generate_html_report import generate_html_report
    from je_web_runner.utils.generate_report.generate_json_report import generate_json_report
    from je_web_runner.utils.generate_report.generate_junit_xml_report import generate_junit_xml_report
    from je_web_runner.utils.generate_report.generate_xml_report import generate_xml_report

    generate_json_report(base_name)
    generate_html_report(base_name)
    generate_xml_report(base_name)
    generate_junit_xml_report(base_name)


def _validate_dir(directory: str, include_tags=None, exclude_tags=None) -> None:
    paths = get_dir_files_as_list(directory)
    if include_tags or exclude_tags:
        paths = filter_paths(paths, include=include_tags, exclude=exclude_tags)
    for path in paths:
        validate_action_file(path)


def _dispatch(args: argparse.Namespace) -> None:
    """Run side-effects requested by the parsed args, in a sensible order."""
    include_tags = _split_csv(args.tag)
    exclude_tags = _split_csv(args.exclude_tag)
    if args.validate:
        validate_action_file(args.validate)
    if args.validate_dir:
        _validate_dir(args.validate_dir, include_tags=include_tags, exclude_tags=exclude_tags)
    if args.execute_file:
        execute_action(read_action_json(args.execute_file))
    if args.execute_dir:
        rerun_only = failed_files(args.rerun_failed) if args.rerun_failed else None
        _run_dir(
            args.execute_dir,
            args.parallel,
            include_tags=include_tags,
            exclude_tags=exclude_tags,
            ledger_path=args.ledger,
            rerun_only=rerun_only,
        )
    if args.execute_str:
        execute_action(_parse_execute_str(args.execute_str))
    if args.report:
        _generate_reports(args.report)


def _has_any_action(args: argparse.Namespace) -> bool:
    return any([
        args.execute_file,
        args.execute_dir,
        args.execute_str,
        args.validate,
        args.validate_dir,
        args.report,
    ])


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Entry point for ``python -m je_web_runner``."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    if not _has_any_action(args):
        raise WebRunnerExecuteException(argparse_get_wrong_data)
    _dispatch(args)
    return 0
