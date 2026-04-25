"""
Lighthouse 跑分器：呼叫官方 ``lighthouse`` Node CLI，回傳分數摘要。
Lighthouse runner. Shells out to the official ``lighthouse`` Node CLI and
parses the JSON output to ``{performance, accessibility, best_practices,
seo, pwa}`` scores (all 0–1).

需要環境內已安裝 ``lighthouse`` (npm install -g lighthouse)。
Requires the lighthouse CLI on PATH (``npm install -g lighthouse``).
"""
from __future__ import annotations

import json
import subprocess  # nosec B404 — controlled args, no shell
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class LighthouseError(WebRunnerException):
    """Raised when the Lighthouse run fails or its output cannot be parsed."""


_DEFAULT_TIMEOUT = 180


def _check_url(url: str) -> str:
    if not isinstance(url, str) or not (url.startswith("http://") or url.startswith("https://")):
        raise LighthouseError(f"URL must be http(s): {url!r}")
    return url


def _build_command(
    url: str,
    output_path: str,
    lighthouse_path: str,
    chrome_flags: Optional[List[str]],
    extra_args: Optional[List[str]],
) -> List[str]:
    cmd: List[str] = [
        lighthouse_path,
        url,
        "--output=json",
        f"--output-path={output_path}",
        "--quiet",
        "--no-enable-error-reporting",
    ]
    if chrome_flags:
        cmd.append(f"--chrome-flags={' '.join(chrome_flags)}")
    if extra_args:
        cmd.extend(extra_args)
    return cmd


def _summarise(report: Dict[str, Any]) -> Dict[str, Any]:
    categories = report.get("categories") or {}

    def _score(key: str) -> Optional[float]:
        bucket = categories.get(key)
        if isinstance(bucket, dict):
            score = bucket.get("score")
            return float(score) if isinstance(score, (int, float)) else None
        return None

    return {
        "performance": _score("performance"),
        "accessibility": _score("accessibility"),
        "best_practices": _score("best-practices"),
        "seo": _score("seo"),
        "pwa": _score("pwa"),
    }


def run_lighthouse(
    url: str,
    output_path: Optional[str] = None,
    lighthouse_path: str = "lighthouse",
    chrome_flags: Optional[List[str]] = None,
    extra_args: Optional[List[str]] = None,
    timeout: int = _DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """
    執行 Lighthouse 並回傳 ``{scores, report_path, raw}``
    Run Lighthouse against ``url`` and return scores plus the raw report.

    :param output_path: 報告 JSON 的儲存位置；None 時用暫存檔
    :param lighthouse_path: ``lighthouse`` 可執行檔路徑（預設依賴 PATH）
    :param chrome_flags: 透過 ``--chrome-flags`` 帶給 headless Chrome 的旗標
    :param extra_args: 直接附加到命令列尾的自訂參數
    """
    safe_url = _check_url(url)
    web_runner_logger.info(f"run_lighthouse: {safe_url}")
    using_tmp = output_path is None
    if using_tmp:
        # ``NamedTemporaryFile`` returns a securely-generated path without
        # the ``mktemp`` race; ``delete=False`` lets the lighthouse CLI
        # write to it before we read it back, and we clean up at the end.
        with tempfile.NamedTemporaryFile(suffix=".lh.json", delete=False) as tmp:
            target = tmp.name
    else:
        target = output_path
    cmd = _build_command(safe_url, target, lighthouse_path, chrome_flags, extra_args)
    try:
        result = subprocess.run(  # nosec B603 — explicit list, shell=False
            cmd,
            timeout=timeout,
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as error:
        raise LighthouseError(
            f"lighthouse CLI not found at {lighthouse_path!r}; install via npm"
        ) from error
    except subprocess.TimeoutExpired as error:
        raise LighthouseError(f"lighthouse timed out after {timeout}s") from error
    if result.returncode != 0:
        raise LighthouseError(
            f"lighthouse exited with {result.returncode}: {result.stderr.strip()[:200]}"
        )
    try:
        raw = json.loads(Path(target).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise LighthouseError(f"failed to read lighthouse report: {error}") from error
    summary = {
        "scores": _summarise(raw),
        "report_path": None if using_tmp else target,
        "raw": raw,
    }
    if using_tmp:
        try:
            Path(target).unlink()
        except OSError:
            pass
    return summary


def assert_scores(result: Dict[str, Any], thresholds: Dict[str, float]) -> None:
    """
    斷言所有指定分數皆達門檻
    Assert each requested category score is at or above its threshold (0–1).
    """
    scores = result.get("scores") if isinstance(result, dict) else None
    if not isinstance(scores, dict):
        raise LighthouseError("lighthouse result missing 'scores' dict")
    breaches: List[Dict[str, Any]] = []
    for category, minimum in thresholds.items():
        value = scores.get(category)
        if value is None:
            breaches.append({"category": category, "value": None, "min": minimum})
            continue
        if value < minimum:
            breaches.append({"category": category, "value": value, "min": minimum})
    if breaches:
        raise LighthouseError(f"lighthouse scores below threshold: {breaches}")
