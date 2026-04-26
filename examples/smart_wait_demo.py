"""
Demo: smart_wait helpers + memory-leak probe against a real SPA-ish page.

- ``wait_for_fetch_idle``     installs a fetch hook on ``window.fetch``
                              and resolves once no requests are in flight
- ``wait_for_spa_route_stable`` watches ``history.pushState`` mutations
- ``memory_leak.detect_growth`` repeatedly drives an action and reports
  the linear-fit slope of ``performance.memory.usedJSHeapSize``

Run: python examples/smart_wait_demo.py
"""
from __future__ import annotations

import sys
import time

from je_web_runner import webdriver_wrapper_instance
from je_web_runner.api.observability import detect_growth
from je_web_runner.api.reliability import (
    wait_for_fetch_idle,
    wait_for_spa_route_stable,
)


TARGET_URL = "https://example.com/"


def main() -> int:
    chrome_args = ["--disable-blink-features=AutomationControlled"]
    try:
        webdriver_wrapper_instance.set_driver("chrome", options=chrome_args)
    except Exception as error:  # pylint: disable=broad-except
        print(f"smart_wait_demo: cannot start chrome ({error!r})", file=sys.stderr)
        return 1

    driver = webdriver_wrapper_instance.current_webdriver
    try:
        webdriver_wrapper_instance.to_url(TARGET_URL)
        time.sleep(1)
        wait_for_fetch_idle(driver, quiet_for=0.3, timeout=10)
        print("fetch idle: OK")
        wait_for_spa_route_stable(driver, quiet_for=0.3, timeout=10)
        print("spa route stable: OK")

        # Memory probe: trigger a tiny DOM mutation N times and measure heap.
        def mutate_dom():
            driver.execute_script(
                "const el = document.createElement('span');"
                "el.textContent = 'tick'; document.body.appendChild(el);"
                "el.remove();"
            )

        try:
            summary = detect_growth(
                driver=driver,
                action=mutate_dom,
                iterations=4,
                warmup=1,
            )
            slope = summary["slope_bytes_per_iter"]
            delta = summary["delta_bytes"]
            print(f"heap slope: {slope:+.1f} B/iter, delta {delta:+,d} B")
        except Exception as error:  # pylint: disable=broad-except
            # performance.memory only exists on Chromium / Edge; some
            # builds (or unsupported browsers) raise here. Log and skip.
            print(f"memory probe skipped: {error!r}")
    finally:
        try:
            webdriver_wrapper_instance.quit()
        except Exception:  # pylint: disable=broad-except  # nosec B110 — best-effort cleanup
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
