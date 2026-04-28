====================================
WebRunner English Documentation
====================================

The English manual is split into chapters that follow a typical reader
journey: install → drive a browser → author actions → scale → integrate.
Use the table of contents on the left, or jump straight to a chapter
below.

.. contents:: On this page
   :local:
   :depth: 1

----

.. _eng-getting-started:

Chapter 1 — Getting Started
===========================

Install WebRunner, run your first browser session, and scaffold a new
project skeleton.

.. toctree::
    :maxdepth: 2
    :caption: Getting Started

    doc/installation/installation_doc.rst
    doc/quick_start/quick_start_doc.rst
    doc/create_project/create_project_doc.rst

.. _eng-core-wrappers:

Chapter 2 — Core Wrappers
=========================

The Selenium-facing facade: drivers, options, elements, and locator
value objects. Read this once and the rest of the framework stops
feeling like magic.

.. toctree::
    :maxdepth: 2
    :caption: Core Wrappers

    doc/architecture/architecture_doc.rst
    doc/webdriver_wrapper/webdriver_wrapper_doc.rst
    doc/webdriver_manager/webdriver_manager_doc.rst
    doc/webdriver_options/webdriver_options_doc.rst
    doc/web_element/web_element_doc.rst
    doc/test_object/test_object_doc.rst

.. _eng-actions:

Chapter 3 — Action Authoring & Execution
========================================

Compose JSON-driven action scripts, register callbacks, plug in custom
packages, and record what the browser did.

.. toctree::
    :maxdepth: 2
    :caption: Actions

    doc/action_executor/action_executor_doc.rst
    doc/assertion/assertion_doc.rst
    doc/callback_function/callback_function_doc.rst
    doc/test_record/test_record_doc.rst
    doc/package_manager/package_manager_doc.rst

.. _eng-backends:

Chapter 4 — Browser Backends
============================

Selenium and Playwright back-ends, plus the lower-level browser glue
(CDP / DevTools, capabilities, network shaping).

.. toctree::
    :maxdepth: 2
    :caption: Backends

    doc/backends/backends_doc.rst
    doc/browser_internals/browser_internals_doc.rst

.. _eng-reporting:

Chapter 5 — Reporting & Observability
=====================================

Generate HTML / JSON / XML reports, ship logs, surface metrics, and
diff trends across runs.

.. toctree::
    :maxdepth: 2
    :caption: Reporting

    doc/generate_report/generate_report_doc.rst
    doc/reports/reports_doc.rst
    doc/observability/observability_doc.rst
    doc/logging/logging_doc.rst

.. _eng-orchestration:

Chapter 6 — Orchestration & Scale
=================================

Parallel runs, sharding, retries, Selenium Grid, and Kubernetes Job
manifests.

.. toctree::
    :maxdepth: 2
    :caption: Orchestration

    doc/orchestration/orchestration_doc.rst

.. _eng-quality:

Chapter 7 — Quality, Security & Data
====================================

Linting, locator scoring, PII redaction, accessibility diffs, contract
testing, and data / auth helpers.

.. toctree::
    :maxdepth: 2
    :caption: Quality & Data

    doc/quality_security/quality_security_doc.rst
    doc/data_auth_api/data_auth_api_doc.rst

.. _eng-tooling:

Chapter 8 — Tooling, CLI & Diagnostics
======================================

Command-line entry points, the remote socket driver, and the
exception hierarchy you will see in tracebacks.

.. toctree::
    :maxdepth: 2
    :caption: Tooling

    doc/cli/cli_doc.rst
    doc/tooling/tooling_doc.rst
    doc/socket_driver/socket_driver_doc.rst
    doc/exception/exception_doc.rst

.. _eng-integrations:

Chapter 9 — Integrations
========================

CI annotations, JIRA / TestRail / Slack notifiers, IDE schema mappings,
and the **Model Context Protocol (MCP)** server that lets Claude drive
WebRunner.

.. toctree::
    :maxdepth: 2
    :caption: Integrations

    doc/integrations/integrations_doc.rst
    doc/mcp_claude/mcp_claude_doc.rst
    doc/cookbook/cookbook_doc.rst

.. _eng-reference:

Chapter 10 — API Reference
==========================

Auto-generated Python API reference and the legacy "extended features"
hub, kept for cross-linking from older guides.

.. toctree::
    :maxdepth: 2
    :caption: Reference

    doc/api_reference/api_reference.rst
    doc/extended_features/extended_features_doc.rst
