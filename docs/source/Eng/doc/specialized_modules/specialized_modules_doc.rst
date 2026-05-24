==================================
Specialized Modules
==================================

A second wave of utility modules ship under ``je_web_runner/utils/``,
each in its own subpackage with focused unit tests. They are not part
of the executor's hot path — import only what a particular test needs.

Every module here is also reachable from action JSON as a ``WR_*``
command when the relevant entry point is wired up; see
:doc:`../action_executor/action_executor_doc` for command registration.

.. contents:: On this page
   :local:
   :depth: 2

----

Web Platform APIs
=================

For modern browser APIs that are awkward to drive through plain
WebDriver: streams, storage, file pickers, notifications.

``webtransport_assert``
-----------------------

HTTP/3 WebTransport datagram + stream frame recorder. Symmetric API
with ``websocket_assert`` and ``sse_assert`` so the assertion code
looks the same regardless of transport.

Key entry points:

* ``WtFrameRecorder.record_sent_datagram(payload)``,
  ``.record_stream_chunk(direction, stream_id, payload, fin=…)``
* ``assert_datagram_count``, ``assert_stream_complete``,
  ``assert_payload_contains``, ``assert_json_shape``

``indexed_db_explorer``
-----------------------

Generates a browser-side harvest script that serialises a chosen
IndexedDB into JSON, plus typed :class:`IdbSnapshot` parser and
``assert_store_present`` / ``assert_record_count`` / ``assert_key_present``
/ ``assert_index_present`` / ``diff_snapshots`` helpers.

``file_system_access``
----------------------

JS shim that mocks ``showOpenFilePicker`` / ``showSaveFilePicker`` /
``showDirectoryPicker``. Records every ``write()`` against the fake
save handle into ``window.__wr_fsa_writes__``; ``parse_writes`` +
``assert_wrote`` + ``combined_payload`` consume the harvested log.

``notifications_audit``
-----------------------

Installs a JS shim that tracks every ``Notification.requestPermission``
call and every ``new Notification(...)``. Asserts:

* ``assert_no_prompt_without_gesture``
* ``assert_no_prompt_before(min_page_age_ms=…)``
* ``assert_no_spam_after_deny``
* ``assert_notification_shown(title_contains=…, body_contains=…, tag=…)``
* ``assert_unique_tags``

``sse_assert``
--------------

Server-Sent Events wire-format parser + chunk-buffering
:class:`SseRecorder`. Assertions: count, data-contains, JSON shape,
strictly-increasing ids.

``websocket_assert``
--------------------

WebSocket frame recorder + count / payload / pubsub-pattern /
JSON-shape assertions.

``webrtc_assert``
-----------------

Ingests JSON snapshots of ``RTCPeerConnection`` instance state and
``getStats()`` reports. Asserts: connected state, track presence, SDP
codec, packet-loss ratio, minimum bytes flowed.

``view_transitions``
--------------------

JS instrumentation that records each ``document.startViewTransition``
lifecycle + ``LayoutShift`` entries scoped to the transition window.
Asserts: ``assert_all_finished``, ``assert_under_duration``,
``assert_cls_under``, ``assert_group_present``.

Security & Headers
==================

``mixed_content_audit``
-----------------------

HAR parser + console-message scanner that flags HTTP resources loaded
on HTTPS pages. Severity bucket: ``ACTIVE`` (blocked outright) vs
``PASSIVE`` (loaded but unsafe) vs ``UPGRADE`` (HSTS-auto-redirected).

``clickjacking_audit``
----------------------

Combined header policy verdict (``X-Frame-Options`` +
``frame-ancestors``) plus an HTML probe page generator so the actual
browser behaviour can be measured even when headers look correct.

``open_redirect_detector``
--------------------------

Eight-payload probe set covering ``//evil``, ``@userinfo``,
``javascript:``, ``data:``, mixed-case bypass, backslash bypass, etc.
Classifies each response as ``BLOCKED`` / ``ALLOWED`` / ``AMBIGUOUS``
against a caller-supplied probe callable.

``sri_verify``
--------------

Parses ``<script>`` / ``<link rel=stylesheet>`` tags and validates the
``integrity=`` attribute: presence, algorithm strength (rejects sha1 /
md5), cross-origin requirement, and (optionally) recomputed hash from
a caller-supplied payload provider.

``coop_coep_audit``
-------------------

Audits the four headers needed for ``crossOriginIsolated`` to be true
(COOP / COEP) plus per-resource ``Cross-Origin-Resource-Policy`` or
CORS satisfying the page's COEP value.

``token_leak_detector``
-----------------------

Scans HAR bodies, log lines, and arbitrary text for leaked credentials:

* JWT (with Base64 header validity check)
* AWS access key + secret-assignment
* GitHub PAT (``ghp_…`` / ``gho_…``)
* Slack bot tokens (``xox[abprs]-…``)
* Stripe live secret (``sk_live_…``)
* Google API key (``AIza…``)
* Bearer header assignments, session-token assignments

``consent_audit``
-----------------

Cookie catalogue covering well-known vendors (Google Analytics,
Facebook Pixel, Hotjar, LinkedIn, Mixpanel, Amplitude, Stripe,
Intercom, CSRF, session). Detects non-essential cookies set before
consent or reintroduced after explicit rejection.

``pii_in_screenshot``
---------------------

OCR + PII regex scanner over rendered screenshots. Catches email,
Luhn-validated credit-card, US SSN, ROC ID, IBAN, IPv4, E.164 phone.
Useful for screenshot bundles that get uploaded to shared dashboards.

Performance Budgets
===================

``inp_tracker``
---------------

Interaction-to-Next-Paint instrumentation: ``PerformanceObserver`` on
``event``-timing + ``first-input``, with rating buckets matching the
Web Vitals thresholds (≤200ms GOOD, ≤500ms NEEDS_WORK, else POOR).

``hydration_check``
-------------------

SSR hydration mismatch detector. DOM diff with framework-attr /
comment stripping for React / Vue / Svelte / Astro / Nuxt, plus a
console-message scanner for the well-known marker strings.

``bundle_budget``
-----------------

Per-asset-kind transfer-byte budget (script / stylesheet / image /
font / media / xhr). Sources from a HAR object; reports per-kind
totals + per-budget breach + biggest-asset ranking.

``third_party_budget``
----------------------

Vendor classification + per-vendor request / byte / blocking-ms
budget, plus a total vendor-count cap. Built-in catalogue of common
analytics / marketing / CX vendors; ``extra_vendors`` extends it.

``long_animation_frame``
------------------------

``long-animation-frame`` PerformanceObserver listener that captures
per-script attribution (forced reflow time, pause time, script source
URL). Asserts: per-frame max + total blocking time.

``console_error_budget``
------------------------

JS console error / unhandled-rejection budget with regex ignore
patterns. Ships Selenium and CDP-event-payload adapters.

Backend Integration
===================

``grpc_tester``
---------------

gRPC stub method wrapper that records every call into a
:class:`GrpcCallRecorder` with status / duration / error. Also ships
length-prefix encode / decode and trailer parser helpers for gRPC-Web.

``webhook_receiver``
--------------------

Stdlib-only threaded HTTP server (random free port) for catching the
app's outbound webhooks during a test. ``wait_for(predicate, timeout)``
+ ``assert_received_path`` / ``assert_received_with_header`` /
``assert_received_json_matching``.

``idempotency_check``
---------------------

Run a request twice; compare status code, body (with
``ignore_body_keys`` for non-deterministic fields), state (via
``state_probe`` callable), and side-effect count. Allow legitimate
409-on-second via ``allow_status_change_to``.

``pagination_audit``
--------------------

Walks every page via a caller-supplied :class:`PageFetcher` until
exhaustion. Reports duplicates across pages, cursor loops,
empty-page indices, hit-max-pages, plus a ``assert_sorted_by``
ordering check across page boundaries.

``backend_log_correlator``
--------------------------

Given a W3C ``traceparent`` captured during a UI run, fetch matching
log lines from Grafana Loki / Elasticsearch / a JSON-lines file and
``attach_to_failure_bundle``.

``email_render``
----------------

MailHog / Mailpit fetch (or local ``.eml`` directory) → typed
:class:`CapturedEmail` → multi-viewport screenshot via pluggable
render driver.

AI / Workflow
=============

``failure_narrator``
--------------------

Loads a failure-bundle directory (meta.json + console.log + dom.html
+ network_errors.log) and prompts an LLM for a natural-language
"why this failed" report. Strict JSON envelope; ``markdown()`` renders
a PR-comment-ready string.

``repro_minimizer``
-------------------

Classic delta-debugging (ddmin) — given a failing action list and a
callable that says "does this still fail?", returns the smallest
still-failing subsequence.

``locator_hardener``
--------------------

Heuristic fragility score (nth-of-type / text-xpath /
hashed-class / deep-descendant / multi-class CLASS_NAME), then asks
an LLM client for stronger alternatives. Safety filter rejects unsafe
selectors from the LLM response.

``test_categorizer``
--------------------

Regex rules over action-name patterns auto-tag each test as some
combination of ``smoke`` / ``regression`` / ``perf`` / ``a11y`` /
``security`` / ``payment`` / ``data_driven`` / ``visual`` / ``api``.
Caller can extend with custom :class:`Rule` instances.

``exploratory_ai``
------------------

Agentic exploratory tester: ``Explorer.run()`` loop drives a
``PageObserver`` + ``ActionPlanner`` protocol pair, gathering
:class:`BugSignal`\\s from observed console / network errors. Ships
``RandomPlanner`` as a deterministic fuzz fallback.

``story_to_actions``
--------------------

LLM-driven translation of a user story (plus optional Figma frame
metadata) into validated WR action JSON. Validator rejects unknown
action names and bad locator strategies before returning.

``session_to_test``
-------------------

rrweb / generic-event-stream → WR action JSON; auto-detects input
format. Falls back to ``WR_comment`` for events that don't map to
known actions.

``test_auto_repair``
--------------------

LLM-driven test rewrite from a failure bundle + git diff context.

``edge_case_generator``
-----------------------

LLM edge-case variant generator complementing ``mutation_testing``.

``multimodal_qa``
-----------------

Send screenshot + question to a vision LLM (Claude Vision / GPT-4o /
local VLM); strict JSON envelope; ``assert_passes(min_confidence=0.6)``
for the gating path.

``prompt_drift_monitor``
------------------------

For apps with their own internal LLM features: capture a baseline of
prompt → answer pairs (with embeddings + must_include /
must_exclude anchors), then ``check_drift(...)`` periodically.

``test_dedup_ai``
-----------------

Structural fingerprint (canonical action signature, stable hash) plus
semantic dedupe (cosine clustering with a pluggable embedder).

``walkthrough_docs``
--------------------

Generate step-by-step SOP / Confluence-style markdown from recorded
runs.

a11y / i18n / Visual
====================

``ocr_assert``
--------------

Tesseract-backed text assertion (``contains`` / ``fuzzy`` / ``any``)
for canvas / WebGL / image content. Whitespace + accent
normalisation built in; cloud OCR adapters can be plugged in via the
:class:`OcrBackend` protocol.

``screen_reader_runner``
------------------------

Walks an accessibility tree (CDP ``Accessibility.getFullAXTree`` or
Playwright snapshot) to simulate NVDA / VoiceOver reading order.
Flags unnamed interactive elements, heading-level skips, missing
``alt``, generic link text ("click here", "more").

``pseudo_localization``
-----------------------

Pseudo-localises strings (``__éxámplé strîng__``), preserving
``{name}`` / ``%d`` / ``<tag>`` placeholders. ``scan_for_hardcoded``
detects rendered strings that came back verbatim despite being
pseudo-localised (= probably hard-coded).

``forced_colors_mode``
----------------------

CDP-features builder for the four CSS media queries: ``color-scheme``,
``reduced-motion``, ``forced-colors``, ``prefers-contrast``.
Computed-style diff with a "became invisible" heuristic.

``visual_ai``
-------------

aHash / dHash / pHash + SSIM-proxy for canvas / chart visual diff.

Governance & Reporting
======================

``pr_risk_score``
-----------------

Fuses flake / impact-analysis / locator-health / coverage signals
into a 0-100 PR risk score. ``is_blocking(block_at=75)`` gate +
markdown report for PR comments.

``flag_matrix``
---------------

Feature-flag combination matrix with ``forbid`` / ``require``
constraints, pinned baselines, deterministic seeded sampling, and a
greedy smallest-failing-subset cover for "all failures involve
checkout=v2"-style triage.

``chaos_hooks``
---------------

Seeded chaos injection: network offline, network slow, CPU throttle,
mid-flow reload, tab background. Deterministic schedule per action
list given a seed.

``db_snapshot``
---------------

Per-test DB savepoint / rollback isolation. Pluggable
:class:`SnapshotBackend` protocol; ships an :class:`InMemoryBackend`
for testing the workflow itself + a context-manager + a pytest
fixture factory.

``time_freezer``
----------------

CDP injection script that patches ``Date``, ``Date.now``, and
``performance.now`` to a frozen or slow-motion clock — for
"this banner expires at midnight UTC" / "session timeout" /
"week-of-year calculation" tests.

``persona_runner``
------------------

Drives ``test_cases × personas`` matrix. ``summary`` flags
persona-specific regressions (only one persona fails) vs file-specific
ones (every persona fails the same test).

``git_bisect_flake``
--------------------

Two modes:

* **Ledger-only** — works directly off the standard run ledger, no
  git access needed
* **Probe-driven** — classic bisect with optional ``known_good`` /
  ``known_bad`` clamping for faster convergence

``test_cost_estimator``
-----------------------

Per-runner rate-card (built-in defaults for Sauce / BrowserStack /
LambdaTest / GitHub Actions Linux + macOS) × ledger minutes → USD +
CO₂ estimate, with per-test breakdown and a top-N costliest-tests
markdown report.

``slack_digest``
----------------

Renders a Slack Block-Kit payload (also a Teams Adaptive Card and a
plain-text fallback) summarising quarantine activity, top-risk PRs,
cost trend, and pass-rate delta for a digest period.

``quarantine_age_report``
-------------------------

Reads the quarantine registry; adds age + tier
(``fresh`` / ``lingering`` / ``stale`` / ``abandoned``) to each
entry. ``assert_no_abandoned`` raises on any entry past 90 days.

``test_debt_dashboard``
-----------------------

Scans the test tree for ``@pytest.mark.skip`` / ``skipif`` / ``xfail``
markers, ``# TODO`` / ``# FIXME`` comments in test bodies, and JSON
``"_skip": true`` markers. Adds age (mtime) and owner (CODEOWNERS).

``sla_tracker``
---------------

"% of suites finishing under N seconds" rolled up by ISO week or day.
Compares against a target pass percentage; ``assert_meets_sla`` is
the CI gate.

``bug_repro_stability``
-----------------------

Repeat a failing probe N times → classify
``deterministic`` / ``flaky`` / ``non_reproducible``. Groups error
signatures, tracks longest pass / fail streak.

``test_owners_map``
-------------------

CODEOWNERS parser (last-match-wins glob semantics) + per-test
override layer (JSON). ``audit_unowned(test_ids, map)`` lists every
test with no resolvable owner.

Earlier governance / quality modules (cross-listed)
---------------------------------------------------

``failure_triage``, ``flake_detector``, ``locator_health``,
``mutation_testing``, ``live_dashboard``, ``test_scheduler`` are
already documented in
:doc:`../quality_security/quality_security_doc` and
:doc:`../observability/observability_doc`; cross-listed here for
discovery.

Other Specialised Modules
=========================

* ``chrome_profile`` — Persistent Chrome profile + stealth +
  snapshot / sync-back.
* ``device_cloud`` — Real-device cloud connector (BrowserStack /
  Sauce / LambdaTest).
* ``otel_bridge`` — W3C traceparent injection for distributed tracing.
* ``otp_interceptor`` — MailHog / Mailpit / IMAP / SMS OTP polling
  for 2FA flows.
* ``download_verify`` — PDF / CSV / Excel / JSON / SHA256 download
  assertions.
* ``openapi_to_e2e`` — OpenAPI / Swagger spec → ``WR_http_*`` action
  JSON generator.
* ``cross_tab_sync`` — Multi-page BroadcastChannel / storage
  propagation asserts.

Where to look next
==================

* :doc:`../quality_security/quality_security_doc` — original quality /
  security helpers (linter, secret scanner, security headers, Lighthouse,
  perf budgets…).
* :doc:`../api_reference/api_reference` — auto-generated Python API
  surface for everything in the table.
* ``CLAUDE.md`` at the repo root — single-source utils tree with the
  full one-line-each module descriptions.
