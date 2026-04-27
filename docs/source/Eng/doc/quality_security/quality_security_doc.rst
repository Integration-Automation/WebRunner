==================
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

Security probes
===============

* ``header_tampering.HeaderTampering()`` — rule list + Playwright
  ``page.route()`` integration to set / remove / append headers.
* ``license_scanner.scan_text(bundle_text)`` — find SPDX identifiers and
  known license phrases; ``assert_allowed_licenses(findings, allow=,
  deny=)`` for SBOM gates.
* ``cookie_consent.ConsentDismisser().dismiss(driver)`` — auto-click
  OneTrust / TrustArc / Cookiebot / Didomi / Quantcast accept buttons.

PII scanner & visual review
===========================

* ``pii_scanner.scan_text(text)`` finds ``email`` / ``phone_e164`` /
  Luhn-checked ``credit_card`` / ``ssn_us`` / checksum-validated
  ``taiwan_id`` / ``ipv4``. ``assert_no_pii`` and ``redact_text`` are
  the CI gate / sanitiser.
* ``visual_review.VisualReviewServer(baseline_dir, current_dir).start()``
  serves a local web UI with side-by-side images and an *Accept current
  as baseline* button (path-traversal guarded).

Form auto-fill / A11y diff
==========================

* ``form_autofill.plan_fill_actions(fields, fixture, submit_locator=...)``
  — infers each field's purpose from ``data-testid`` / ``id`` / ``name``
  / ``placeholder`` / ``label`` / ``type`` and emits a runnable action
  sequence.
* ``accessibility.a11y_diff.diff_violations(baseline, current)`` —
  buckets axe-core findings into ``added`` / ``resolved`` /
  ``persisting`` keyed on ``(rule_id, target)``;
  ``assert_no_regressions(diff)`` is the CI gate.
