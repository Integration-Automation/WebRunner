"""
Replay studio：把 record list + 失敗截圖串成單一 HTML 時間軸。
Compose ``test_record_instance`` records and any failure screenshots into a
single self-contained HTML timeline so triage can scan a run at a glance.
"""
from __future__ import annotations

import html
from pathlib import Path
from typing import Any, Dict, List, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.utils.test_record.test_record_class import test_record_instance


class ReplayStudioError(WebRunnerException):
    """Raised when the studio cannot be written."""


_NO_EXCEPTION = "None"


def _matching_screenshot(name: str, screenshot_dir: Optional[Path]) -> Optional[Path]:
    if screenshot_dir is None or not screenshot_dir.is_dir():
        return None
    for png in sorted(screenshot_dir.glob(f"*_{name}.png")):
        return png
    return None


def _row_html(record: Dict[str, Any], screenshot: Optional[Path]) -> str:
    function_name = record.get("function_name", "(unknown)")
    failed = record.get("program_exception", _NO_EXCEPTION) != _NO_EXCEPTION
    status_class = "fail" if failed else "ok"
    status_label = "FAILED" if failed else "PASSED"
    parts: List[str] = [
        f"<tr class='{status_class}'>",
        f"<td>{html.escape(str(record.get('time', '')))}</td>",
        f"<td>{html.escape(str(function_name))}</td>",
        f"<td><span class='badge {status_class}'>{status_label}</span></td>",
        f"<td><pre>{html.escape(str(record.get('local_param') or ''))}</pre></td>",
        f"<td><pre>{html.escape(str(record.get('program_exception') or ''))}</pre></td>",
    ]
    if screenshot is not None:
        href = html.escape(str(screenshot.as_posix()))
        parts.append(
            f"<td><a href='{href}' target='_blank'>"
            f"<img src='{href}' alt='shot' class='shot'></a></td>"
        )
    else:
        parts.append("<td></td>")
    parts.append("</tr>")
    return "".join(parts)


def build_replay_html(
    records: Optional[List[Dict[str, Any]]] = None,
    screenshot_dir: Optional[str] = None,
    title: str = "WebRunner replay",
) -> str:
    """
    產生 self-contained HTML 報告字串
    Build a single HTML document with a timeline table of records and
    inline references to any matching failure screenshots.
    """
    web_runner_logger.info("build_replay_html")
    actual_records = records if records is not None else list(test_record_instance.test_record_list)
    shots_dir = Path(screenshot_dir) if screenshot_dir else None
    rows = []
    for record in actual_records:
        rows.append(_row_html(record, _matching_screenshot(
            str(record.get("function_name", "")), shots_dir,
        )))
    return _DOC_TEMPLATE.format(
        title=html.escape(title),
        rows="\n".join(rows),
        count=len(actual_records),
    )


def export_replay_studio(
    output_path: str,
    records: Optional[List[Dict[str, Any]]] = None,
    screenshot_dir: Optional[str] = None,
    title: str = "WebRunner replay",
) -> str:
    """Write the studio to ``output_path`` and return the resolved path."""
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    body = build_replay_html(records=records, screenshot_dir=screenshot_dir, title=title)
    try:
        target.write_text(body, encoding="utf-8")
    except OSError as error:
        raise ReplayStudioError(f"failed to write replay studio: {error}") from error
    return str(target.resolve())


_DOC_TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>{title}</title>
<style>
body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif;
        margin: 1rem; background: #fafafa; color: #222; }}
table {{ border-collapse: collapse; width: 100%; background: white; }}
th, td {{ border: 1px solid #e5e5e5; padding: 6px 10px; vertical-align: top;
         font-size: 13px; }}
th {{ background: #f3f3f3; text-align: left; }}
tr.fail td {{ background: #fff4f4; }}
pre {{ margin: 0; white-space: pre-wrap; word-break: break-word;
       max-height: 8em; overflow: auto; }}
.shot {{ max-width: 220px; height: auto; border: 1px solid #ddd; }}
.badge {{ padding: 2px 6px; border-radius: 3px; font-weight: 600; }}
.badge.ok {{ background: #d6f5d6; color: #1f5f1f; }}
.badge.fail {{ background: #fdd; color: #7c1f1f; }}
</style></head>
<body>
<h1>{title}</h1>
<p>{count} action records.</p>
<table>
<thead><tr>
<th>Time</th><th>Action</th><th>Status</th><th>Params</th><th>Exception</th><th>Screenshot</th>
</tr></thead>
<tbody>
{rows}
</tbody>
</table>
</body></html>
"""
