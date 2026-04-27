=======
Tooling
=======

Reliability helpers
===================

* ``adaptive_retry.run_with_retry(fn, policy=...)`` — retries only when
  the failure classifier labels the exception transient / flaky /
  environment; ``RetryPolicy`` exposes per-category budgets and history.
* ``linter.locator_strength.score_locator(strategy, value)`` — scores a
  locator on a 0–100 scale; ``score_action_locators`` runs across an
  action JSON list.
* ``smart_wait.wait_for_fetch_idle`` / ``wait_for_spa_route_stable`` —
  inject window.fetch and history hooks to detect SPA quiescence.
* ``throttler.throttle("payments-api")`` — file-semaphore for cross-shard
  concurrency limits.

Browser pool / BiDi bridge
==========================

* ``browser_pool.BrowserPool(factory, size=N).warm()`` /
  ``pool.session() as ses`` — pre-warmed browser instances with health
  check + recycle policy.
* ``bidi_backend.BidiBridge().subscribe(target, event, callback)`` —
  unified BiDi-style event subscription against either Selenium 4 BiDi
  (``driver.script.add_console_message_handler``) or Playwright
  ``page.on(...)``. ``register_translator`` extends the event list.

HAR replay server
=================

* ``har_replay.load_har("recorded.har")`` parses ``log.entries`` from a
  HAR file.
* ``HarReplayServer(entries).start()`` boots a local HTTP server that
  serves the recorded responses; URL patterns support literal /
  ``*`` glob / ``re:`` regex with rotation across duplicates.

Test impact analysis
====================

``impact_analysis.build_index("./actions")`` walks every action JSON
file and projects locator names, URLs, template names, and ``WR_*``
command names into a reverse index. Combine with
``sharding.diff_shard`` for a smarter test selection:

.. code-block:: python

   from je_web_runner.utils.impact_analysis import (
       affected_action_files, build_index,
   )

   index = build_index("./actions")
   to_run = affected_action_files(index, locators=["primary_cta"])

Workspace bootstrapper / driver pinner
======================================

* ``bootstrapper.init_workspace("./my-tests")`` — drops sample actions,
  ledger, schema, pre-commit hook, GitHub Actions workflow.
* ``driver_pin.install_for_browser(pin_file, browser)`` — read a JSON
  pin file (``name`` / ``version`` / ``url`` / ``archive_format`` /
  ``binary_inside``), fetch + cache once, return the binary path. No
  GitHub API rate-limit dependency.

Selenium → Playwright translator
================================

* ``sel_to_pw.translate_python_source(text)`` — rewrites common
  ``driver.find_element(By.X, ...).send_keys(...)``-style lines into
  ``page.locator(...).fill(...)`` equivalents; returns
  ``Translation(line, original, translated, note)`` per hit.
* ``sel_to_pw.translate_action_list(actions)`` — rewrites ``WR_*`` action
  JSON to ``WR_pw_*`` (drops ``WR_implicitly_wait`` since Playwright
  auto-waits).

Action formatter / Markdown authoring
=====================================

* ``action_formatter.format_actions(actions)`` — canonical multi-line
  JSON, kwargs in preferred-then-alphabetical order; ``format_file(path)``
  reformats in place and returns ``(text, changed)``.
* ``md_authoring.parse_markdown(text)`` — bullet templates: ``open
  <url>``, ``click <selector>``, ``type "<text>" into <selector>``,
  ``wait <n>s``, ``assert title "<text>"``, ``press <Key>``,
  ``screenshot``, ``run template <name>``, ``quit``. Unrecognised lines
  become ``WR__note`` entries.

Page Object codegen
===================

``pom_codegen.discover_elements_from_html(html)`` walks every element
with ``data-testid`` / ``id`` / form ``name`` and emits a Python module
with one ``TestObject`` property per element via ``render_pom_module``.

Coverage map
============

* ``coverage_map.build_coverage_map("./actions")`` — reverse index of
  ``WR_to_url`` paths (numeric / UUID segments collapsed to ``:id``);
  ``coverage.uncovered(declared_routes)`` flags missing routes.

WR_sleep
========

The executor exposes ``WR_sleep`` so action JSON pipelines can pace
themselves natively without resorting to ``WR_execute_async_script``
``setTimeout`` tricks:

.. code-block:: json

   [
     ["WR_to_url", {"url": "https://example.com"}],
     ["WR_sleep", {"seconds": 2.5}],
     ["WR_get_screenshot_as_png"]
   ]

Negative or non-numeric ``seconds`` raise ``ValueError`` so a typo can't
silently no-op the pipeline.
