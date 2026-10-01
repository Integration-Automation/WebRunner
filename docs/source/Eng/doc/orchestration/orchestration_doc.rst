==================
Test orchestration
==================

* **Tag filter** — ``meta.tags`` on action files, CLI ``--tag`` /
  ``--exclude-tag``.
* **Dependencies** — ``meta.depends_on`` (basenames); the runner builds a
  topological order and skips downstream files when an upstream fails.
* **Run ledger** — ``--ledger ledger.json`` records pass/fail per file;
  ``--rerun-failed ledger.json`` re-runs only the previously failed ones.
* **Flaky detection** — ``flaky_paths(ledger.json, min_runs=3)`` over the
  ledger history.
* **Sharding** — ``--shard INDEX/TOTAL`` partitions files deterministically
  by SHA-1 path hash.
* **Multi-user matrix** — ``run_for_users(action, [(name, setup), …])``
  runs the same actions per user context and returns step-level diffs.
* **A/B mode** — ``run_ab(action, setup_a, setup_b)`` runs the same actions
  against two environments and diffs the resulting record sequences.
* **Watch mode** — ``--watch DIR`` re-runs ``--execute_dir`` whenever JSON
  files change (debounced).
* **Scheduler** — stdlib-sched-backed ``ScheduledRunner`` for simple
  intervals.

Async execution
===============

``--parallel-mode async`` (or ``AsyncExecutor`` from Python) runs action
files on asyncio: one headless Chromium and, per file, a fresh browser
context, so concurrent files are separate users (cookies, storage, tabs).
``--parallel N`` caps how many run at once; Playwright is required.

* ``WR_apw_*`` commands act in the file's own context: navigation, clicks,
  input, text and title reads and assertions, waits, tabs
  (``WR_apw_new_page`` / ``WR_apw_switch_to_page`` / ``WR_apw_close_page``),
  screenshots, ``WR_apw_evaluate`` (behind the arbitrary-script gate),
  ``WR_apw_sleep`` and WebSocket frames
  (``WR_apw_websocket_messages`` / ``WR_apw_wait_for_websocket_message``).
* Any other ``WR_*`` command runs in a worker thread with the usual gates,
  retries and failure screenshots, sharing the process-wide singletons as
  ``--parallel-mode thread`` does.
* ``AsyncExecutor.run(actions)`` returns ``(record, failed)``;
  ``run_many(lists, concurrency)`` runs lists with ``asyncio.gather``.

Orchestration & DX
==================

* ``action_templates.render_template("login_basic", {...})`` —
  built-in templates: ``login_basic``, ``accept_cookies``,
  ``switch_locale``, ``close_modal``; ``register_template`` for custom.
* ``sharding.diff_shard.select_for_changed(candidates, base_ref="main")``
  — git-diff-aware test selection.
* ``watch_mode.watch_loop(directory, on_change=callback)`` — polled file
  watcher with snapshot diff.
* ``k8s_runner.render_job_manifests(ShardJobConfig(...))`` /
  ``render_job_yaml(config)`` — one ``batch/v1 Job`` per shard.
* ``perf_metrics.budgets`` — ``load_budgets("budgets.json")`` +
  ``evaluate_metrics(route, metrics, budgets)`` +
  ``assert_within_budget(result)``.

Fan-out / event bus / extension harness
=======================================

* ``fanout.run_fan_out([(name, callable)…], max_workers=4)`` — parallel
  task runner returning per-task duration + outcome, ``fail_fast``
  optional.
* ``event_bus.EventBus(log_path).publish(topic, payload)`` — file-backed
  ndjson pub/sub; ``poll(offset, topics=...)`` and
  ``wait_for(topic, predicate, timeout=30)`` for cross-shard coordination.
* ``extension_harness.parse_manifest("./ext")`` — MV2 / MV3 manifest
  reader; ``apply_to_chrome_options`` and
  ``playwright_persistent_context_args`` plug into either backend.

CLI & orchestration polish
==========================

* ``test_filter.name_filter.filter_paths(paths, include=[...],
  exclude=[...])`` — regex-based path selector orthogonal to tags.
* ``process_supervisor.ProcessSupervisor().kill_orphans()`` — walk the
  OS process table for ``chromedriver`` / ``geckodriver`` /
  ``msedgedriver`` and kill stragglers; ``with_watchdog(fn, 300)``
  enforces a wall-clock deadline.
* ``pipeline.load_pipeline({"stages": [...]})`` + ``run_pipeline`` —
  multi-stage gates with optional ``continue_on_failure``.
