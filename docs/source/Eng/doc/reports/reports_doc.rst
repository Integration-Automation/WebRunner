=======
Reports
=======

Five formats plus a manifest:

* HTML — single ``<base>.html`` (success / failure rows in one document).
* JSON — split ``<base>_success.json`` + ``<base>_failure.json``.
* XML — split ``<base>_success.xml`` + ``<base>_failure.xml``.
* JUnit XML — single ``<base>_junit.xml`` (CI-native).
* Allure — directory of ``<uuid>-result.json`` files (Allure CLI input).

``generate_all_reports(base, allure_dir=None)`` runs every generator and
writes ``<base>.manifest.json`` mapping each format to the actual paths
produced — downstream CI globs no longer need format-specific knowledge.

Reporting & CI extras
=====================

* ``pr_comment.post_or_update_comment(repo, pr_number, body, token=)``
  — idempotent via a hidden HTML marker.
* ``trend_dashboard.compute_trend("ledger.json")`` +
  ``render_html(trend)`` — daily pass-rate / duration / SVG chart.

CI reproducibility & long-term observability
============================================

* ``workspace_lock.build_lock(drivers=..., playwright_versions={"chromium":
  "127.0.0.0"})`` — snapshots every Python distribution + driver +
  Playwright browser version; ``write_lock`` / ``diff_locks`` round-trip.
* ``a11y_trend.aggregate_history(history)`` + ``render_html(points)``
  — per-day per-impact axe-violation count, self-contained SVG chart.
* ``perf_drift.detect_drift({"lcp_ms": samples}, baseline_window=20,
  recent_window=5, tolerance=0.1)`` — sliding-window P95 drift
  detection; ``assert_no_regression(report)`` is the strict path.
