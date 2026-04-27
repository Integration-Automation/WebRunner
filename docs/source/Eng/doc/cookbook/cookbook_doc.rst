==============================
Cookbook, tiers & API façade
==============================

Cookbook examples
=================

The ``examples/`` directory ships runnable recipes that drive real Chrome
end-to-end. Each found a real bug the unit suite missed:

* ``counting_stars.{py,json}`` — open YouTube and play OneRepublic
  Counting Stars; revealed the bug where
  ``webdriver_wrapper.execute_script`` was swallowing return values.
* ``google_search.py`` — consent dismissal + result heading scrape.
* ``form_submit.py`` — ``form_autofill.plan_fill_actions`` +
  ``state_diff.capture_state`` round trip against ``httpbin``.
* ``smart_wait_demo.py`` — ``wait_for_fetch_idle``,
  ``wait_for_spa_route_stable``, ``memory_leak.detect_growth``.
* ``fanout_demo.py`` — parallel HTTP preflights via ``run_fan_out``.
* ``pii_redact_demo.py`` — pure-logic ``scan_text`` / ``redact_text``.

Test tiers
==========

* ``test/unit_test/`` — 1200 mock-based unit tests, ~12s.
* ``test/integration_test/`` — 30 wired-modules tests with real I/O
  (in-memory SQLite, in-process HTTP servers, real subprocesses for
  the MCP / LSP). Surfaced the Windows LSP CRLF framing bug.
* ``test/e2e_test/`` — six real-browser smoke tests; skips cleanly when
  ``WEBRUNNER_E2E_HUB`` doesn't resolve. Use
  ``cd docker && docker compose up -d`` locally;
  ``.github/workflows/e2e_browser.yml`` runs them daily / on demand.

Thematic façade
===============

The 80+ helpers under ``je_web_runner.utils.<area>`` are also re-exported
under ``je_web_runner.api`` grouped by theme:

.. code-block:: python

   from je_web_runner.api import (
       authoring, debugging, frontend, infra, mobile,
       networking, observability, quality, reliability,
       security, test_data,
   )

The original Selenium-flavoured top-level surface stays unchanged so
existing user code keeps working.
