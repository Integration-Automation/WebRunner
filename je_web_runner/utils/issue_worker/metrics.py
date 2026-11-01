"""Local delivery history, queue health and offline interactive reporting; no platform requests."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from statistics import mean
import time
from typing import Any

from je_web_runner.utils.issue_worker.store import IssueStore
from je_web_runner.utils.issue_worker.types import ACTIVE, FINAL, IssueSnapshot, IssueWorkerError


class IssueMetrics:
    """Separate recorded delivery outcomes from legacy observations and business acceptance."""

    def __init__(self, store: IssueStore) -> None:
        self.store = store

    def summary(self, since_hours: float | None = None, issue: str | None = None) -> dict[str, Any]:
        """Aggregate immutable run/revision outcomes; never infer unrecorded historical successes."""
        cutoff = self._cutoff(since_hours)
        if issue is not None:
            source, _separator, external_id = issue.partition(":")
            IssueSnapshot(source, external_id, "", "", "")
        with self.store.connection() as connection:
            rows = connection.execute("SELECT payload,recorded FROM outcomes WHERE recorded>=? "
                                      "AND (? IS NULL OR job_key=?) ORDER BY recorded",
                                      (cutoff, issue, issue)).fetchall()
            tracked = {tuple(row) for row in connection.execute("SELECT job_key,run,revision FROM outcomes")}
            since = connection.execute("SELECT value FROM settings WHERE name='metrics_since'").fetchone()["value"]
        outcomes = [{**json.loads(row["payload"]), "recorded": row["recorded"]} for row in rows]
        groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        daily: dict[tuple[str, str], Counter] = defaultdict(Counter)
        for item in outcomes:
            groups[(item["source"], item["kind"])].append(item)
            day = datetime.fromtimestamp(item["recorded"], timezone.utc).date().isoformat()
            daily[(day, item["source"])][item["status"]] += 1
        failures = Counter(item["reason_code"] for item in outcomes if item["status"] != "awaiting_review")
        failure_groups = Counter((item["source"], item["reason_code"]) for item in outcomes
                                 if item["status"] != "awaiting_review")
        queue, legacy = self._queue(tracked, issue)
        return {"generated": time.time(), "recording_since": float(since), "since_hours": since_hours, "issue": issue,
                "business_acceptance": "not_measured", "summary": _aggregate(outcomes),
                "groups": [{"source": source, "kind": kind, **_aggregate(items)}
                           for (source, kind), items in sorted(groups.items())],
                "failures": [{"reason_code": code, "count": count} for code, count in failures.most_common()],
                "failure_groups": [{"source": source, "reason_code": code, "count": count}
                                   for (source, code), count in failure_groups.most_common()],
                "daily": [{"date": day, "source": source, **counts} for (day, source), counts in sorted(daily.items())],
                "queue": queue, "legacy_observations": legacy, "recent": outcomes[-50:]}

    def write_report(self, base: str | Path, since_hours: float | None = None,
                     report: dict[str, Any] | None = None, issue: str | None = None) -> tuple[str, str]:
        """Write one consistent JSON/HTML snapshot, with no CDN or external assets."""
        report = report if report is not None else self.summary(since_hours, issue)
        base = Path(base)
        base.parent.mkdir(parents=True, exist_ok=True)
        json_path = base.with_name(base.name + ".json")
        html_path = base.with_name(base.name + ".html")
        payload = json.dumps(report, ensure_ascii=False, indent=2)
        json_path.write_text(payload, encoding="utf-8")
        encoded = payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
        html_path.write_text(_HTML.replace("__PAYLOAD__", encoded), encoding="utf-8")
        return str(json_path.resolve()), str(html_path.resolve())

    def _queue(self, tracked: set[tuple], issue: str | None) -> tuple[dict[str, Any], int]:
        counts: Counter = Counter()
        observed: Counter = Counter()
        legacy = 0
        with self.store.connection() as connection:
            for job in connection.execute("SELECT key,run,status,suitable,data FROM jobs WHERE ? IS NULL OR key=?",
                                          (issue, issue)):
                data = json.loads(job["data"])
                counts[job["status"]] += 1
                counts["held"] += int(job["status"] == "queued" and not job["suitable"])
                counts["pending_reports"] += int(bool(data.get("report_pending")))
                active = job["status"] not in FINAL
                counts["deferred_environment"] += int(bool(data.get("environment_error")) and active)
                counts["deferred_platform"] += int(bool(data.get("platform_error")) and active)
                counts["review_blocked"] += int(bool(data.get("review_blocked")))
                observed[data.get("review_closed", "open" if data.get("pr") else "none")] += 1
                identity = (job["key"], job["run"], data.get("review_rounds", 0))
                legacy += int(job["status"] in FINAL and identity not in tracked)
        return {"statuses": dict(counts), "active": sum(counts[status] for status in ACTIVE),
                "observed_pr_states": dict(observed)}, legacy

    @staticmethod
    def _cutoff(since_hours: float | None) -> float:
        if since_hours is None:
            return 0
        if isinstance(since_hours, bool) or not isinstance(since_hours, (int, float)) or \
                not math.isfinite(since_hours) or since_hours <= 0:
            raise IssueWorkerError("since_hours must be finite and positive")
        return time.time() - since_hours * 3600


def _aggregate(outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(item["status"] for item in outcomes)
    duration = [item["duration_seconds"] for item in outcomes if item["duration_seconds"] is not None]
    return {"attempts": len(outcomes), "delivered": counts["awaiting_review"], "outcomes": dict(counts),
            "delivery_rate": counts["awaiting_review"] / len(outcomes) if outcomes else None,
            "mean_duration_seconds": mean(duration) if duration else None, "duration_samples": len(duration),
            "tools": sum(item["tool_count"] for item in outcomes),
            "validation_rounds": sum(item["validation_rounds"] for item in outcomes)}


_HTML = """<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Issue automation report</title>
<style>
body{font:16px system-ui;margin:2rem auto;max-width:1100px;padding:0 1rem;background:#f5f7fa;color:#172b4d}
section{background:white;border-radius:12px;padding:1.2rem;margin:1rem 0;border:1px solid #dfe5ed}
table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:.6rem;border-bottom:1px solid #eee}
select{font:inherit;padding:.4rem}.bar{background:#117d6b;height:14px;border-radius:3px;display:inline-block}
.muted{color:#52657a}h1{margin-bottom:.4rem}#totals{font-size:1.25rem}td:last-child{overflow-wrap:anywhere}
</style><h1>Issue automation</h1><p class="muted">Delivery evidence and local queue state</p>
<p>Source <select id="source"><option value="">All sources</option></select></p>
<section><p id="totals"></p><p id="coverage" class="muted"></p>
<p>Delivery means a PR ready for human review was produced. Business acceptance is not measured.</p></section>
<section><h2>By task kind</h2><table><thead><tr><th>Source</th><th>Kind</th><th>Attempts</th>
<th>Delivered</th><th>Rate</th><th>Mean duration (s)</th></tr></thead><tbody id="groups"></tbody></table></section>
<section><h2>Daily deliveries (UTC)</h2><div id="daily"></div></section>
<section><h2>Why attempts stopped</h2><table><thead><tr><th>Reason</th><th>Count</th></tr></thead>
<tbody id="failures"></tbody></table></section>
<section><h2>Recent outcomes</h2><table><thead><tr><th>Issue</th><th>Run/revision</th><th>Outcome</th>
<th>Reason</th></tr></thead><tbody id="recent"></tbody></table></section>
<section><h2>Local queue</h2><pre id="queue"></pre></section>
<script id="data" type="application/json">__PAYLOAD__</script><script>
const report=JSON.parse(document.getElementById('data').textContent);
const control=document.getElementById('source');
for(const source of [...new Set(report.groups.map(x=>x.source))].sort()){
  const option=document.createElement('option');option.value=source;option.textContent=source;control.append(option);
}
function row(target,values){const line=document.createElement('tr');
  for(const value of values){const cell=document.createElement('td');cell.textContent=String(value);line.append(cell);}
  document.getElementById(target).append(line);
}
function render(){const selected=control.value;
  const groups=report.groups.filter(x=>!selected||x.source===selected);
  const attempts=groups.reduce((sum,x)=>sum+x.attempts,0),delivered=groups.reduce((sum,x)=>sum+x.delivered,0);
  document.getElementById('totals').textContent=`${delivered} delivered / ${attempts} recorded attempts`;
  document.getElementById('coverage').textContent=
    `${report.legacy_observations} legacy observations excluded from rates`;
  document.getElementById('groups').replaceChildren();
  for(const item of groups)row('groups',[item.source,item.kind,item.attempts,item.delivered,
    item.delivery_rate===null?'—':(item.delivery_rate*100).toFixed(1)+'%',
    item.mean_duration_seconds===null?'—':item.mean_duration_seconds.toFixed(1)]);
  const days=new Map();for(const item of report.daily.filter(x=>!selected||x.source===selected))
    days.set(item.date,(days.get(item.date)||0)+(item.awaiting_review||0));
  const maximum=Math.max(1,...days.values());document.getElementById('daily').replaceChildren();
  for(const [date,count] of [...days.entries()].sort()){
    const line=document.createElement('p'),bar=document.createElement('span');bar.className='bar';
    bar.style.width=(count/maximum*60)+'%';line.textContent=date+'  '+count+'  ';line.append(bar);
    document.getElementById('daily').append(line);
  }
  const failures=new Map();for(const item of report.failure_groups.filter(x=>!selected||x.source===selected))
    failures.set(item.reason_code,(failures.get(item.reason_code)||0)+item.count);
  document.getElementById('failures').replaceChildren();
  for(const [reason,count] of [...failures.entries()].sort((left,right)=>right[1]-left[1]))
    row('failures',[reason,count]);
  document.getElementById('recent').replaceChildren();
  for(const item of report.recent.filter(x=>!selected||x.source===selected).slice().reverse())
    row('recent',[item.key,item.run+'/'+item.revision,item.status,item.reason_code+': '+item.reason]);
  document.getElementById('queue').textContent=JSON.stringify(report.queue,null,2);
}
control.addEventListener('change',render);render();
</script></html>"""
