"""
統一產生所有報告並產出 manifest，記錄每個格式實際寫出的檔案路徑。
Run every report generator at once and emit a manifest listing the actual
output paths so downstream CI globs aren't surprised by per-format
naming differences.

各格式輸出形狀（規格決定，不會統一）：
File-output convention per format (driven by the format spec, intentionally
different):

- JSON:   ``<base>_success.json`` + ``<base>_failure.json`` (pass/fail split)
- XML:    ``<base>_success.xml``  + ``<base>_failure.xml``  (pass/fail split)
- HTML:   ``<base>.html``                                   (single combined file)
- JUnit:  ``<base>_junit.xml``                              (JUnit spec is single file)
- Allure: ``<allure_dir>/<uuid>-result.json`` (× N)         (Allure CLI input shape)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.generate_report.generate_allure_report import generate_allure_report
from je_web_runner.utils.generate_report.generate_html_report import generate_html_report
from je_web_runner.utils.generate_report.generate_json_report import generate_json_report
from je_web_runner.utils.generate_report.generate_junit_xml_report import generate_junit_xml_report
from je_web_runner.utils.generate_report.generate_xml_report import generate_xml_report
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class ReportManifestError(WebRunnerException):
    """Raised when manifest generation cannot proceed."""


def expected_paths(base_name: str, allure_dir: Optional[str] = None) -> Dict[str, List[str]]:
    """
    回傳每個格式預期寫出的路徑（實際是否存在由 manifest 確認）
    Return the paths every generator is expected to produce. Whether each
    file actually got written is confirmed in :func:`generate_all_reports`.
    """
    paths: Dict[str, List[str]] = {
        "json": [f"{base_name}_success.json", f"{base_name}_failure.json"],
        "xml": [f"{base_name}_success.xml", f"{base_name}_failure.xml"],
        "html": [f"{base_name}.html"],
        "junit": [f"{base_name}_junit.xml"],
    }
    if allure_dir:
        paths["allure"] = [str(allure_dir)]
    return paths


def _existing(paths: List[str]) -> List[str]:
    return [path for path in paths if Path(path).exists()]


def generate_all_reports(
    base_name: str,
    allure_dir: Optional[str] = None,
    write_manifest: bool = True,
) -> Dict[str, Any]:
    """
    依預設慣例產出所有報告；回傳 ``{format: [paths produced]}`` 與 manifest 路徑
    Run every report generator under a single base name and return a dict of
    format → list of paths actually produced. When ``write_manifest`` is
    True (default), also write ``<base>.manifest.json`` capturing the same
    information.

    :param base_name: 共用前綴（不含副檔名） / shared base name (no extension)
    :param allure_dir: Allure 輸出目錄；None 時不產生 Allure
                       Allure output directory; ``None`` skips Allure.
    :param write_manifest: 是否寫出 manifest 檔 / whether to write the manifest
    :return: dict 包含 ``produced``（依格式列出實際存在的路徑）與
             ``manifest_path``（manifest 檔位置或 None）
    """
    web_runner_logger.info(f"generate_all_reports base={base_name}")
    plan = expected_paths(base_name, allure_dir=allure_dir)
    errors: Dict[str, str] = {}

    # Each generator may raise when there are no records; track but continue.
    for label, run in (
        ("json", lambda: generate_json_report(base_name)),
        ("xml", lambda: generate_xml_report(base_name)),
        ("html", lambda: generate_html_report(base_name)),
        ("junit", lambda: generate_junit_xml_report(base_name)),
    ):
        try:
            run()
        except Exception as error:  # noqa: BLE001 — collect all generator errors
            errors[label] = repr(error)
            web_runner_logger.warning(f"generate_all_reports[{label}] failed: {error!r}")

    allure_paths: List[str] = []
    if allure_dir:
        try:
            allure_paths = generate_allure_report(allure_dir) or []
        except Exception as error:  # noqa: BLE001
            errors["allure"] = repr(error)

    produced: Dict[str, List[str]] = {
        "json": _existing(plan["json"]),
        "xml": _existing(plan["xml"]),
        "html": _existing(plan["html"]),
        "junit": _existing(plan["junit"]),
    }
    if allure_dir:
        produced["allure"] = allure_paths or _existing(plan.get("allure", []))

    manifest_path: Optional[str] = None
    if write_manifest:
        manifest_path = f"{base_name}.manifest.json"
        try:
            payload = {
                "base_name": base_name,
                "produced": produced,
                "errors": errors,
            }
            Path(manifest_path).write_text(
                json.dumps(payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as error:
            web_runner_logger.error(f"generate_all_reports manifest write failed: {error!r}")
            manifest_path = None

    return {
        "produced": produced,
        "errors": errors,
        "manifest_path": manifest_path,
    }
