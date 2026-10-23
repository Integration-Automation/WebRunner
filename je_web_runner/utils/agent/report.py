"""Local JSON and escaped HTML reports for browser agent outcomes."""
from __future__ import annotations

import html
import json
from pathlib import Path

from je_web_runner.utils.agent.types import AgentReport


def write_agent_report(report: AgentReport, base_name: str | Path) -> list[str]:
    """Write BASE.agent.json and BASE.agent.html, returning their absolute paths."""
    base = Path(base_name)
    base.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report.to_dict(), indent=2, ensure_ascii=False)
    json_path = Path(str(base) + ".agent.json")
    html_path = Path(str(base) + ".agent.html")
    json_path.write_text(payload + "\n", encoding="utf-8")
    html_path.write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8"><title>WebRunner agent report</title>'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<h1>WebRunner agent report</h1><p>Status: ' + html.escape(report.status) + '</p><pre>'
        + html.escape(payload) + '</pre></html>\n', encoding="utf-8",
    )
    return [str(json_path.resolve()), str(html_path.resolve())]
