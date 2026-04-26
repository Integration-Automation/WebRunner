"""
頁面效能指標擷取：FCP / LCP / CLS / TTFB / DOMContentLoaded / load。
Page performance metrics: FCP / LCP / CLS / TTFB / domContentLoaded / load.

採用 PerformanceObserver；LCP / CLS 需要等一小段時間累積，因此呼叫者可指定
等待秒數。
Uses PerformanceObserver in the page; LCP / CLS need a short observation
window so callers can specify the wait duration.
"""
from __future__ import annotations

from typing import Any, Dict

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.webdriver.playwright_wrapper import playwright_wrapper_instance
from je_web_runner.webdriver.webdriver_wrapper import webdriver_wrapper_instance


class PerfMetricsError(WebRunnerException):
    """Raised when metrics cannot be collected."""


_COLLECT_JS_TEMPLATE = r"""
(function(observeMs, done) {
  var out = {};
  try {
    var nav = performance.getEntriesByType('navigation')[0];
    if (nav) {
      out.ttfb = nav.responseStart - nav.requestStart;
      out.dom_content_loaded = nav.domContentLoadedEventEnd;
      out.load = nav.loadEventEnd;
    }
    var paints = performance.getEntriesByType('paint');
    for (var i = 0; i < paints.length; i++) {
      if (paints[i].name === 'first-contentful-paint') out.fcp = paints[i].startTime;
    }
  } catch (e) { out.error = String(e); }

  var lcp = 0;
  var cls = 0;
  var lcpObs, clsObs;
  try {
    lcpObs = new PerformanceObserver(function(list) {
      var entries = list.getEntries();
      if (entries.length) lcp = entries[entries.length - 1].startTime;
    });
    lcpObs.observe({type: 'largest-contentful-paint', buffered: true});
  } catch (e) {}
  try {
    clsObs = new PerformanceObserver(function(list) {
      var entries = list.getEntries();
      for (var i = 0; i < entries.length; i++) {
        if (!entries[i].hadRecentInput) cls += entries[i].value;
      }
    });
    clsObs.observe({type: 'layout-shift', buffered: true});
  } catch (e) {}

  setTimeout(function() {
    out.lcp = lcp;
    out.cls = cls;
    try { if (lcpObs) lcpObs.disconnect(); } catch (e) {}
    try { if (clsObs) clsObs.disconnect(); } catch (e) {}
    done(out);
  }, observeMs);
})
"""


def selenium_collect_metrics(observe_ms: int = 1000) -> Dict[str, Any]:
    """
    透過 ``execute_async_script`` 抓取效能指標
    Collect performance metrics via Selenium ``execute_async_script``.
    """
    web_runner_logger.info(f"selenium_collect_metrics observe_ms={observe_ms}")
    driver = webdriver_wrapper_instance.current_webdriver
    if driver is None:
        raise PerfMetricsError("no Selenium driver active")
    script = (
        "var done = arguments[arguments.length - 1];"
        f"({_COLLECT_JS_TEMPLATE})({int(observe_ms)}, done);"
    )
    return driver.execute_async_script(script) or {}


def playwright_collect_metrics(observe_ms: int = 1000) -> Dict[str, Any]:
    """
    透過 ``page.evaluate`` 抓取效能指標
    Collect performance metrics via Playwright's ``page.evaluate``.
    """
    web_runner_logger.info(f"playwright_collect_metrics observe_ms={observe_ms}")
    page = playwright_wrapper_instance.page
    expression = (
        f"async (observeMs) => {{ "
        f"  return await new Promise(function(resolve) {{ "
        f"    ({_COLLECT_JS_TEMPLATE})(observeMs, resolve); "
        f"  }}); "
        f"}}"
    )
    return page.evaluate(expression, observe_ms) or {}


def assert_metrics_within(metrics: Dict[str, Any], thresholds: Dict[str, float]) -> None:
    """
    斷言所有指標都不超過上限
    Assert each measured metric is at or below its threshold (ms / score).

    :param metrics: ``{"fcp": ..., "lcp": ..., "cls": ...}``
    :param thresholds: ``{"fcp": 2000, "lcp": 2500, "cls": 0.1}``
    """
    breaches = []
    for key, limit in thresholds.items():
        value = metrics.get(key)
        if value is None:
            continue
        if value > limit:
            breaches.append({"metric": key, "value": value, "limit": limit})
    if breaches:
        raise PerfMetricsError(f"perf metrics over budget: {breaches}")
