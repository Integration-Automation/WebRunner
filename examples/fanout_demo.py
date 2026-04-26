"""
Demo: parallel HTTP preflights via ``fanout.run_fan_out``.

Real e2e tests often need to confirm half a dozen backend services are
healthy before driving the browser. ``run_fan_out`` parallelises the
checks and reports per-task duration / outcome.

Run: python examples/fanout_demo.py
"""
from __future__ import annotations

import sys
import time
import urllib.error
import urllib.request

from je_web_runner.api.infra import run_fan_out


PREFLIGHTS = [
    ("httpbin",     "https://httpbin.org/get"),
    ("example",     "https://example.com/"),
    ("slow-anchor", "https://httpbin.org/delay/1"),
]


def _fetch_status(url: str) -> int:
    request = urllib.request.Request(url, method="GET")
    request.add_header("User-Agent", "WebRunner-cookbook/0.1")
    with urllib.request.urlopen(request, timeout=10) as response:  # nosec B310 — example fixture
        return int(response.status)


def main() -> int:
    tasks = [
        (name, lambda u=url: _fetch_status(u))
        for name, url in PREFLIGHTS
    ]
    started = time.monotonic()
    result = run_fan_out(tasks, max_workers=4)
    wall = time.monotonic() - started
    print(f"fan-out wall time: {wall:.2f}s for {len(result.outcomes)} tasks")
    for outcome in sorted(result.outcomes, key=lambda o: o.name):
        print(
            f"  {outcome.name:<14} "
            f"{'ok' if outcome.succeeded else 'FAIL':<5} "
            f"in {outcome.duration_seconds:.2f}s "
            f"-> {outcome.result if outcome.succeeded else outcome.error}"
        )
    if not result.succeeded:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
