=================
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

Browser & locale
================

* ``device_emulation`` — ``available_presets`` /
  ``playwright_kwargs("iPhone 15 Pro")`` /
  ``apply_to_chrome_options(opts, "Desktop 1080p")`` /
  ``cdp_emulation_command(name)``.
* ``geo_locale.GeoOverride`` — yields both
  ``cdp_payloads(override)`` and ``playwright_context_kwargs(override)``.
* ``multi_tab.TabChoreographer`` — track tabs by alias;
  ``register_current`` / ``open_new`` / ``switch_to`` / ``with_tab`` /
  ``close``.
* ``webauthn.enable_virtual_authenticator(driver)`` — CDP
  ``WebAuthn.addVirtualAuthenticator`` for passkey simulation.

Storybook / shadow DOM
======================

* ``storybook.discover_stories(index_or_path)`` reads Storybook 7+
  ``index.json``;
  ``plan_actions_for_stories(stories, base_url, run_a11y=True,
  capture_screenshot=True, extra_per_story=...)`` builds a flat action
  plan that visits each story under ``iframe.html?id=...`` and runs
  axe / screenshot.
* ``storybook.visual_snapshots.capture_story_snapshots(stories,
  base_url, take_screenshot, navigate, baseline_dir=...)`` — per-story
  PNG capture with byte-level baseline comparison.
* ``dom_traversal.shadow_pierce.find_first(driver, css_selector)`` /
  ``find_all`` walk open shadow roots recursively. ``execute_script``
  for Selenium, ``evaluate`` for Playwright; ``assert_pierced_visible``
  raises if the selector doesn't match anywhere.

CDP tap / cross-browser / state diff
====================================

* ``cdp_tap.CdpRecorder(output_path).attach(driver)`` — wraps
  ``execute_cdp_cmd`` so every call is appended to an ndjson log;
  ``CdpReplayer(load_recording(path))`` plays the same sequence back.
* ``cross_browser.diff_runs([chromium_run, firefox_run, webkit_run])``
  — buckets findings into ``major`` / ``minor`` (5xx → major,
  screenshot hash → minor); ``assert_parity(report, only_major=True)``
  is the CI gate.
* ``state_diff.capture_state(driver)`` snapshots cookies +
  localStorage + sessionStorage; ``diff_states(before, after)`` reports
  added / removed / changed keys per section.
