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

The detailed feature documentation is split across these subtopic pages:

The chapters below own these subtopics in the main TOC; this hidden
toctree only keeps the cross-references resolvable for older guides
that link in via ``extended_features``.

.. toctree::
   :hidden:

   ../architecture/architecture_doc.rst
   ../backends/backends_doc.rst
   ../reports/reports_doc.rst
   ../observability/observability_doc.rst
   ../orchestration/orchestration_doc.rst
   ../quality_security/quality_security_doc.rst
   ../browser_internals/browser_internals_doc.rst
   ../data_auth_api/data_auth_api_doc.rst
   ../integrations/integrations_doc.rst
   ../tooling/tooling_doc.rst
   ../cookbook/cookbook_doc.rst
