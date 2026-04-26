==================================
Extended features
==================================

Beyond the original Selenium wrapper, WebRunner ships a Playwright backend, a
JSON-driven action executor, and a wide collection of orchestration,
observability, security, and AI helpers. Every helper is callable from
Python and registered on the executor as a ``WR_*`` command for action JSON
use.

The full, auto-generated command reference (signature + summary for every
``WR_*`` registration) lives at:

    docs/reference/command_reference.md

A JSON Schema describing the action JSON format is exported alongside it:

    docs/reference/webrunner-action-schema.json

Architecture
============

System overview
---------------

.. mermaid::

   flowchart LR
     A1["Action JSON"] --> EXE["Executor"]
     A2["Recorder"] --> A1
     A3["LLM NL → draft"] --> A1
     EXE --> SEL["Selenium"]
     EXE --> PW["Playwright"]
     EXE --> APM["Appium"]
     EXE --> HTTP["HTTP API"]
     EXE --> DB["Database"]
     SEL --> REC["Records"]
     PW --> REC
     REC --> REP["Reports"]
     REC --> OBS["Observability"]
     REC --> NOT["Notifiers"]

Action lifecycle
----------------

.. mermaid::

   flowchart LR
     IN["[cmd, args, kwargs]"] --> VAL["Validator"]
     VAL --> ENV["${ENV.X} / ${ROW.x}"]
     ENV --> SPAN["OTel span"]
     SPAN --> RETRY["Retry policy"]
     RETRY --> GATE["Script gate"]
     GATE --> DISP["event_dict[cmd]"]
     DISP --> RECORD["records.append"]
     DISP -- failure --> SHOT["Auto screenshot"]

Backends
========

Selenium (default)
------------------

The original ``WebDriverWrapper`` plus ``WebElementWrapper``. All commands
without a more specific prefix dispatch here.

Playwright
----------

A full mirror of the Selenium surface lives under ``WR_pw_*``:

* Lifecycle / pages / navigation
* Find (with ``TestObject`` translation) and direct page-level shortcuts
* Element-level wrapper
* Mobile emulation, locale, timezone, geolocation, permissions, clock
* HAR recording, route mocking, console + network event capture
* Network throttling presets via CDP

Switch is opt-in: existing scripts keep running on Selenium.

Cloud Grid
----------

Provider helpers for BrowserStack, Sauce Labs, and LambdaTest:

* ``connect_browserstack`` / ``connect_saucelabs`` / ``connect_lambdatest``
* ``build_browserstack_capabilities`` / ``build_saucelabs_capabilities`` /
  ``build_lambdatest_capabilities``
* ``start_remote_driver`` for arbitrary hub URLs

Appium (mobile)
---------------

``start_appium_session`` builds an Appium WebDriver and registers it on the
shared Selenium wrapper so existing ``WR_*`` commands keep working against a
mobile session. Capability builders cover both Android (UiAutomator2) and
iOS (XCUITest).

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

Quality & security
==================

* **Action linter** — ``WR_lint_action`` warns about legacy command names,
  hard-coded URLs, dangerous scripts, missing tags, duplicate consecutive
  actions.
* **Migration helper** — ``python -m je_web_runner --migrate ./actions``
  rewrites legacy aliases to the preferred names.
* **Hard-coded secrets scanner** — ``scan_action_file`` catches common
  credential / token patterns.
* **HTTP security headers audit** — ``audit_url`` checks HSTS / CSP /
  X-Frame-Options / X-Content-Type-Options / Referrer-Policy /
  Permissions-Policy.
* **Accessibility audit** — ``axe-core`` injection helpers; user supplies
  the source file via ``load_axe_source(path)``.
* **Lighthouse runner** — shells out to the official ``lighthouse`` CLI;
  ``assert_scores`` enforces budgets.
* **Page perf metrics** — ``selenium_collect_metrics`` /
  ``playwright_collect_metrics`` (FCP / LCP / CLS / TTFB).
* **Visual regression** — ``capture_baseline`` / ``compare_with_baseline``
  (Pillow soft dependency).
* **Snapshot testing** — ``match_snapshot`` / ``update_snapshot`` (text /
  DOM with unified-diff mismatch).
* **Network throttling** — ``selenium_emulate_network("slow_3g")`` /
  ``playwright_emulate_network("offline")`` (CDP).
* **Arbitrary-script gate** — ``executor.set_allow_arbitrary_script(False)``
  blocks ``WR_execute_script`` / ``WR_execute_async_script`` /
  ``WR_pw_evaluate`` / ``WR_cdp`` / ``WR_pw_cdp`` for untrusted action JSON.

Browser internals
=================

* **CDP** — ``selenium_cdp`` / ``playwright_cdp`` raw passthroughs.
* **Storage** — ``localStorage`` / ``sessionStorage`` / ``IndexedDB`` get /
  set / clear via injected JS.
* **Service worker / cache** — unregister / clear caches /
  ``Network.setBypassServiceWorker``.
* **Console + network capture** — Playwright event listeners with
  assertions (``no console errors`` / ``no 5xx``).
* **Shadow DOM** — selector chains pierce nested shadow roots.
* **iframes** — switch chains and Playwright frame-locator chains.
* **File upload / download** — element ``send_keys`` / ``set_input_files``
  for upload; ``wait_for_download`` polls a directory for completed files.
* **Browser extension loaders** — Chrome ``add_extension`` / Playwright
  ``--load-extension``.

Test data
=========

* **Faker integration** — ``fake_email`` / ``fake_name`` / ``fake_value`` and
  friends; ``faker`` is a soft dependency.
* **Factories** — ``Factory(defaults)`` evaluates callable defaults per
  ``build()``; pre-built ``user_factory`` / ``order_factory`` /
  ``product_factory``.
* **Testcontainers** — ``start_postgres`` / ``start_redis`` /
  ``start_generic`` wrap testcontainers-python.
* **.env loader + ${ENV.X}** — ``load_env`` / ``expand_in_action`` so the
  same actions can target dev / staging / prod.
* **Data-driven runner** — ``load_dataset_csv`` / ``load_dataset_json`` /
  ``run_with_dataset`` with ``${ROW.col}`` placeholder expansion.

Auth, API, database
===================

* **OAuth2 / OIDC** — ``client_credentials_token`` / ``password_grant_token``
  / ``refresh_token_grant`` with in-process token cache that refreshes 30 s
  before expiry.
* **HTTP API** — ``http_get`` / ``http_post`` / ``http_put`` / ``http_patch``
  / ``http_delete`` plus ``http_assert_status`` and
  ``http_assert_json_contains``.
* **Database** — ``db_query`` / ``db_assert_count`` / ``db_assert_value`` /
  ``db_assert_exists`` / ``db_assert_empty``; SQLAlchemy soft dependency,
  bound parameters only.

Recorder
========

JS-injection recorder (no CDP, cross-browser): captures click / change
events and emits a ``WR_*`` action JSON draft. Sensitive fields
(``type=password``, names matching password / card / cvv / ssn / secret /
token / api_key / otp / passcode, 13–19-digit values) are masked by
default.

CI / integrations
=================

* **GitHub Actions annotations** — ``emit_failure_annotations`` /
  ``emit_from_junit_xml`` produce ``::error file=…::`` lines.
* **JIRA / TestRail** — ``jira_create_failure_issues`` /
  ``testrail_send_results`` for post-run sync.
* **Slack / generic webhook** — ``notify_run_summary``.
* **Selenium Grid 4 docker-compose** — ``docker/docker-compose.yml`` ships
  hub + Chrome + Firefox nodes.
* **IDE configs** — ``docs/ide/vscode-settings.example.json`` and
  ``docs/ide/jetbrains-jsonschemamapping.example.xml`` wire the action JSON
  schema into VS Code / JetBrains.

AI assistance
=============

WebRunner ships **no built-in LLM client**. ``set_llm_callable(fn)``
registers any ``Callable[[str], str]`` and powers:

* ``suggest_locator(html, description)`` — last-resort locator suggestion.
* ``llm_self_heal_locator(name, html_provider)`` — pluggable hook for the
  self-healing locator flow.
* ``generate_actions_from_prompt(request)`` — natural language → action
  JSON draft.
