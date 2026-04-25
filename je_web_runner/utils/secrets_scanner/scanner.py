"""
靜態掃描 action JSON 內常見的硬編密碼 / token。
Scan action JSON for common hard-coded credentials and tokens before they
end up committed.

不能保證找到所有秘密；目標是抓住絕大多數常見格式並避免明顯的疏忽。
Not exhaustive — aims to catch the obvious leaks (AWS / GitHub / Slack /
JWT / generic high-entropy strings on suspicious keys).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class SecretsFound(WebRunnerException):
    """Raised when ``assert_no_secrets`` finds any leaked credentials."""


_SUSPICIOUS_KEY_RE = re.compile(
    r"(password|secret|token|api[-_]?key|private[-_]?key|passwd|credential)",
    re.IGNORECASE,
)

_PATTERNS: List[Dict[str, Any]] = [
    {"id": "aws_access_key", "regex": re.compile(r"\bAKIA[0-9A-Z]{16}\b")},
    {"id": "github_token", "regex": re.compile(r"\bghp_[A-Za-z0-9]{36}\b")},
    {"id": "github_oauth", "regex": re.compile(r"\bgho_[A-Za-z0-9]{36}\b")},
    {"id": "slack_token", "regex": re.compile(r"\bxox[abps]-[A-Za-z0-9-]{10,}\b")},
    {"id": "slack_webhook", "regex": re.compile(r"https://hooks\.slack\.com/services/[A-Za-z0-9/]+")},
    {"id": "jwt", "regex": re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")},
    {"id": "google_api_key", "regex": re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")},
    {"id": "private_key", "regex": re.compile(r"-----BEGIN (?:(?:RSA|EC|DSA|OPENSSH) )?PRIVATE KEY-----")},
]


def _looks_high_entropy(value: str) -> bool:
    """Heuristic: long base64-ish strings without whitespace / variable refs."""
    if "${ENV." in value or "${ROW." in value:
        return False
    if len(value) < 24:
        return False
    if not re.fullmatch(r"[A-Za-z0-9+/=_-]{24,}", value):
        return False
    distinct = len(set(value))
    return distinct >= 12


def _scan_string(value: str, path: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for pattern in _PATTERNS:
        if pattern["regex"].search(value):
            findings.append({"path": path, "rule": pattern["id"], "preview": value[:60]})
    return findings


def _scan_value_for_key(key: str, value: Any, path: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    if not isinstance(value, str):
        return findings
    if _SUSPICIOUS_KEY_RE.search(key) and _looks_high_entropy(value):
        findings.append({"path": path, "rule": "suspicious_key_high_entropy", "preview": value[:60]})
    return findings


def _walk(data: Any, path: str, findings: List[Dict[str, Any]]) -> None:
    if isinstance(data, str):
        findings.extend(_scan_string(data, path))
        return
    if isinstance(data, dict):
        for key, value in data.items():
            child_path = f"{path}.{key}" if path else str(key)
            findings.extend(_scan_value_for_key(str(key), value, child_path))
            _walk(value, child_path, findings)
        return
    if isinstance(data, (list, tuple)):
        for index, item in enumerate(data):
            _walk(item, f"{path}[{index}]", findings)


def scan_action(data: Any) -> List[Dict[str, Any]]:
    """
    掃描 action 結構，回傳所有疑似秘密的位置
    Scan an action structure and return a list of {path, rule, preview} findings.
    """
    web_runner_logger.info("scan_action")
    findings: List[Dict[str, Any]] = []
    _walk(data, "", findings)
    return findings


def scan_action_file(path: str) -> List[Dict[str, Any]]:
    """讀取 action JSON 檔並掃描 / Load an action JSON file and scan it."""
    file_path = Path(path)
    if not file_path.exists():
        raise WebRunnerException(f"action file not found: {path}")
    with open(file_path, encoding="utf-8") as action_file:
        data = json.load(action_file)
    return scan_action(data)


def assert_no_secrets(data: Any) -> None:
    """掃描並在有發現時拋例外 / Scan and raise ``SecretsFound`` on any hit."""
    findings = scan_action(data)
    if findings:
        raise SecretsFound(f"hard-coded secrets detected: {findings}")
