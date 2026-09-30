"""
互動式 HTML 報告 / A self-contained, interactive HTML report of one run.

One file, no external resources and no script: every section expands with ``<details>``.

* **Timeline**: every recorded step in order, failures first-class, with the screenshots
  from ``screenshot_dir`` placed where they were taken (the time in a failure screenshot's
  name, ``<YYYYmmdd_HHMMSS_ffffff>_<command>.png``, else the file's modification time) and
  embedded as data URIs.
* **Errors**: each failure's exception in full; an assertion message that compares two
  values (``a != b``, ``expected X but got Y``) also shows their unified diff.
* **Network waterfall**: the entries of a HAR 1.2 file (``har_path``) as bars on one time
  axis, with method, status, duration and URL.
* **Accessibility**: an axe-core result (``a11y_results``: the dict, or a JSON file path)
  as violation counts by impact and the violations themselves.

Every recorded value is escaped.
"""
from __future__ import annotations

import base64
import datetime
import difflib
import html
import json
import re
from pathlib import Path
from typing import Any

from je_web_runner.utils.exception.exceptions import WebRunnerHTMLException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.utils.test_record.test_record_class import test_record_instance

_IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
_SHOT_NAME = re.compile(r"^(\d{8}_\d{6}_\d{6})_")
_REPR = re.compile(r"(?s)^\w+\((['\"])(.*)\1\)$")
_COMPARISON = re.compile(r"(?s)^(?:[^\n]*?:\s*)?(.+?)\s*!=\s*(.+)$|expected\s+(.+?)\s+but\s+(?:got|was)\s+(.+)$")
_IMPACTS = ("critical", "serious", "moderate", "minor")
_CSS = """
body{font:15px/1.5 system-ui,sans-serif;margin:0;background:#f6f7f9;color:#1d2330}
main{max-width:1100px;margin:0 auto;padding:24px 16px}h1{margin:0 0 4px}h2{margin:28px 0 8px}
.summary{display:flex;gap:12px;flex-wrap:wrap}.pill{padding:4px 12px;border-radius:999px;background:#e4e7ec}
.pass{background:#d7f2de}.fail{background:#fbd9d7}details{background:#fff;border:1px solid #d9dde3;
border-radius:8px;margin:6px 0;padding:6px 12px}summary{cursor:pointer}.step-fail{border-left:5px solid #d93025}
.step-pass{border-left:5px solid #1e8e3e}.time{color:#5f6b7a;font-size:13px}pre{white-space:pre-wrap;
word-break:break-word;background:#f1f3f5;padding:8px;border-radius:6px}.diff-add{color:#1e8e3e}
.diff-del{color:#d93025}img.shot{max-width:100%;border:1px solid #d9dde3;border-radius:6px}
.wf{display:grid;grid-template-columns:70px 60px 70px 1fr 2fr;gap:4px 8px;align-items:center;font-size:13px}
.bar-track{background:#eef0f3;height:10px;border-radius:5px;position:relative}.bar{position:absolute;
height:10px;border-radius:5px;background:#4c8bf5}.bar.err{background:#d93025}.url{overflow:hidden;
text-overflow:ellipsis;white-space:nowrap}.badge{padding:2px 10px;border-radius:6px;color:#fff}
.critical{background:#8b0000}.serious{background:#d93025}.moderate{background:#e37400}.minor{background:#5f6b7a}
""".strip()


def _escape(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _parse_time(text: str) -> datetime.datetime | None:
    try:
        return datetime.datetime.fromisoformat(str(text))
    except ValueError:
        return None


def _screenshots(screenshot_dir: str | None) -> list[tuple[datetime.datetime, Path]]:
    """Every image in ``screenshot_dir`` with the time it was taken, oldest first."""
    if not screenshot_dir:
        return []
    directory = Path(screenshot_dir)
    if not directory.is_dir():
        raise WebRunnerHTMLException(f"screenshot_dir is not a directory: {screenshot_dir!r}")
    shots = []
    for path in directory.iterdir():
        if path.suffix.lower() not in _IMAGE_TYPES or not path.is_file():
            continue
        match = _SHOT_NAME.match(path.name)
        taken = (datetime.datetime.strptime(match.group(1), "%Y%m%d_%H%M%S_%f") if match
                 else datetime.datetime.fromtimestamp(path.stat().st_mtime))
        shots.append((taken, path))
    return sorted(shots)


def _shot_html(path: Path) -> str:
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return (f"<figure><img class='shot' alt='{_escape(path.name)}' "
            f"src='data:{_IMAGE_TYPES[path.suffix.lower()]};base64,{data}'>"
            f"<figcaption class='time'>{_escape(path.name)}</figcaption></figure>")


def _exception_message(recorded: str) -> str:
    """The message inside a recorded ``repr(exception)`` (``Error('a\\nb')``), line breaks restored."""
    match = _REPR.match(recorded.strip())
    return match.group(2).replace("\\n", "\n") if match else recorded


def _comparison_diff(recorded: str) -> str:
    """A unified diff of the two sides of ``a != b`` / ``expected X but got Y``, or ``""``."""
    match = _COMPARISON.search(_exception_message(recorded).strip())
    if not match:
        return ""
    left, right = (match.group(1), match.group(2)) if match.group(1) else (match.group(3), match.group(4))
    lines = difflib.unified_diff(str(left).splitlines(), str(right).splitlines(), "expected", "actual", lineterm="")
    rendered = []
    for line in lines:
        rendered.append(f"<span class='{_diff_class(line)}'>{_escape(line)}</span>")
    return f"<pre>{chr(10).join(rendered)}</pre>" if rendered else ""


def _diff_class(line: str) -> str:
    if line.startswith(("---", "+++", "@@")):
        return ""
    return {"+": "diff-add", "-": "diff-del"}.get(line[:1], "")


def _step_html(number: int, record: dict[str, Any], shots: list[str]) -> str:
    failed = record.get("program_exception") not in (None, "None")
    exception = str(record.get("program_exception"))
    details = f"<p>Parameters</p><pre>{_escape(record.get('local_param'))}</pre>"
    if failed:
        details += f"<p>Error</p><pre>{_escape(exception)}</pre>{_comparison_diff(exception)}"
    return (f"<details class='step-{'fail' if failed else 'pass'}'{' open' if failed else ''}><summary>"
            f"#{number} <b>{_escape(record.get('function_name'))}</b> "
            f"<span class='time'>{_escape(record.get('time'))}</span>{' — failed' if failed else ''}</summary>"
            f"{details}{''.join(shots)}</details>")


def _timeline(records: list[dict[str, Any]], shots: list[tuple[datetime.datetime, Path]]) -> str:
    """Steps in order; each screenshot goes under the last step recorded at or before it."""
    placed: dict[int, list[str]] = {}
    unplaced: list[str] = []
    times = [_parse_time(record.get("time")) for record in records]
    for taken, path in shots:
        owner = max((i for i, time in enumerate(times) if time is not None and time <= taken), default=None)
        (unplaced if owner is None else placed.setdefault(owner, [])).append(_shot_html(path))
    steps = "".join(_step_html(i + 1, record, placed.get(i, [])) for i, record in enumerate(records))
    before = f"<details open><summary>Screenshots before the first step</summary>{''.join(unplaced)}</details>"
    return (before if unplaced else "") + steps


def _waterfall(har_path: str | None) -> str:
    if not har_path:
        return ""
    try:
        entries = json.loads(Path(har_path).read_text(encoding="utf-8"))["log"]["entries"]
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise WebRunnerHTMLException(f"har_path is not a readable HAR 1.2 file: {error!r}") from error
    timed = [(_parse_time(entry.get("startedDateTime", "").replace("Z", "+00:00")), entry) for entry in entries]
    timed = [(start, entry) for start, entry in timed if start is not None]
    if not timed:
        return "<h2>Network waterfall</h2><p>The HAR file has no timed entries.</p>"
    origin = min(start for start, _entry in timed)
    span = max((start - origin).total_seconds() * 1000 + float(entry.get("time") or 0) for start, entry in timed) or 1
    rows = []
    for start, entry in sorted(timed, key=lambda item: item[0]):
        offset = (start - origin).total_seconds() * 1000
        duration = float(entry.get("time") or 0)
        status = (entry.get("response") or {}).get("status")
        status = status if isinstance(status, int) else 0
        request = entry.get("request") or {}
        rows.append(
            f"<span>{_escape(request.get('method', ''))}</span><span>{_escape(status)}</span>"
            f"<span>{duration:.0f} ms</span><div class='bar-track'><div class='bar{' err' if status >= 400 else ''}' "
            f"style='left:{offset / span * 100:.2f}%;width:{max(duration / span * 100, 0.5):.2f}%'></div></div>"
            f"<span class='url' title='{_escape(request.get('url', ''))}'>{_escape(request.get('url', ''))}</span>")
    return (f"<h2>Network waterfall</h2><details open><summary>{len(rows)} requests over {span:.0f} ms</summary>"
            f"<div class='wf'>{''.join(rows)}</div></details>")


def _accessibility(a11y_results: dict[str, Any] | str | None) -> str:
    if not a11y_results:
        return ""
    results = a11y_results
    if isinstance(results, str):
        try:
            results = json.loads(Path(results).read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise WebRunnerHTMLException(f"a11y_results is not a readable axe JSON file: {error!r}") from error
    violations = results.get("violations") if isinstance(results, dict) else None
    if not isinstance(violations, list):
        raise WebRunnerHTMLException("a11y_results must be an axe-core result with a 'violations' list")
    counts = {impact: sum(1 for item in violations if item.get("impact") == impact) for impact in _IMPACTS}
    badges = "".join(f"<span class='badge {impact}'>{impact}: {count}</span> " for impact, count in counts.items())
    items = "".join(
        f"<details><summary><span class='badge {_escape(item.get('impact') or 'minor')}'>"
        f"{_escape(item.get('impact'))}</span> {_escape(item.get('id'))}: {_escape(item.get('help'))}</summary>"
        f"<pre>{_escape(chr(10).join(str(node.get('target')) for node in item.get('nodes') or []))}</pre></details>"
        for item in violations)
    return f"<h2>Accessibility</h2><p>{badges}</p>{items}"


def generate_interactive_html(screenshot_dir: str | None = None, har_path: str | None = None,
                              a11y_results: dict[str, Any] | str | None = None) -> str:
    """
    產生互動式 HTML 報告字串
    The interactive report of the recorded steps as one HTML string (see the module doc).
    """
    records = list(test_record_instance.test_record_list)
    if not records:
        raise WebRunnerHTMLException("no test record to report; enable it with test_record_instance.set_record_enable")
    failures = sum(1 for record in records if record.get("program_exception") not in (None, "None"))
    summary = (f"<div class='summary'><span class='pill'>{len(records)} steps</span>"
               f"<span class='pill pass'>{len(records) - failures} passed</span>"
               f"<span class='pill {'fail' if failures else 'pass'}'>{failures} failed</span></div>")
    body = (f"<h1>Test report</h1>{summary}<h2>Timeline</h2>{_timeline(records, _screenshots(screenshot_dir))}"
            f"{_waterfall(har_path)}{_accessibility(a11y_results)}")
    return (f"<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'><title>Test report</title>"
            f"<style>{_CSS}</style></head><body><main>{body}</main></body></html>")


def generate_interactive_html_report(html_name: str = "default_name", screenshot_dir: str | None = None,
                                     har_path: str | None = None,
                                     a11y_results: dict[str, Any] | str | None = None) -> str:
    """
    產生並寫出互動式 HTML 報告
    Write :func:`generate_interactive_html` to ``<html_name>.html`` and return that path.
    """
    web_runner_logger.info(f"generate_interactive_html_report, html_name: {html_name}")
    target = Path(f"{html_name}.html")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(generate_interactive_html(screenshot_dir, har_path, a11y_results), encoding="utf-8")
    return str(target)
