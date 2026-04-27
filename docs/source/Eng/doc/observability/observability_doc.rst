=============
Observability
=============

* **Failure auto-screenshot** — set
  ``executor.set_failure_screenshot_dir(path)``; failed actions write a PNG
  named ``<timestamp>_<command>.png`` and the path is appended to the
  execution record.
* **Retry policy** — ``executor.set_retry_policy(retries, backoff)``; linear
  backoff between attempts, propagates the original error after the final
  retry.
* **OpenTelemetry** — ``install_executor_tracing("svc")`` registers a span
  factory so every action becomes a span. ``opentelemetry-sdk`` is a soft
  dependency.
* **Live progress dashboard** — ``start_dashboard("127.0.0.1", 8080)``
  serves a tiny stdlib HTTP page that polls the records every second.
* **Replay studio** — ``export_replay_studio(out, screenshot_dir=…)``
  composes records + matching failure screenshots into a single HTML
  timeline.
* **HAR diff** — ``diff_har_files(left, right)`` reports added / removed /
  status-changed requests across two HAR documents.

Observability tooling
=====================

* ``observability.timeline.build(spans=, console=, responses=)`` —
  merges three event sources into a chronological list.
* ``failure_bundle.FailureBundle("test", error_repr).write("bundle.zip")``
  — replayable zip with manifest (``screenshot`` / ``dom`` / ``console``
  / ``network`` / ``trace`` / arbitrary text & files).
* ``memory_leak.detect_growth(driver, action, iterations=10)`` —
  performance.memory linear-fit slope; ``growth_bytes_per_iter_budget``
  raises on regression.
* ``trace_recorder.TraceRecorder().start(context, name) / .stop(context)``
  — Playwright tracing wrapper that always emits a ``.zip``.
* ``csp_reporter.CspViolationCollector`` — securitypolicyviolation
  listener with ``assert_none`` / ``assert_no_directive``.

Triage & production observability
=================================

* ``failure_cluster.cluster_failures(failures, top_n=5)`` — group
  failures by normalised error signature (strip timestamps, hex,
  paths, line numbers, large numerics, quoted substrings).
* ``synthetic_monitoring.SyntheticMonitor(alert_sink).register(name,
  check, failure_threshold=2)`` — edge-triggered alerts on transitions;
  ``run_for(iterations, interval_seconds)`` for the loop.
* ``observability.otlp_exporter.configure_otlp_export(provider,
  OtlpExportConfig(endpoint="https://otlp:4317"))`` — register an OTLP
  ``BatchSpanProcessor`` with an existing ``TracerProvider``;
  ``protocol="grpc"`` (default) or ``"http"``.
