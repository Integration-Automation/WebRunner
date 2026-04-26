"""
Thematic façade for the WebRunner extended utilities.

The top-level :mod:`je_web_runner` namespace already exports the original
Selenium-flavoured surface. The 50+ helpers added during the recent waves
are grouped here by theme so callers can ``from je_web_runner.api import
reliability`` rather than memorising deep import paths.

Each submodule re-exports the public functions of the underlying
``je_web_runner.utils.<X>`` package without doing any additional logic.
This keeps the façade trivial to maintain (one ``__all__`` per topic) and
lets advanced users still reach into the underlying modules when needed.
"""
from je_web_runner.api import (
    authoring,
    debugging,
    frontend,
    infra,
    mobile,
    networking,
    observability,
    quality,
    reliability,
    security,
    test_data,
)

__all__ = [
    "authoring",
    "debugging",
    "frontend",
    "infra",
    "mobile",
    "networking",
    "observability",
    "quality",
    "reliability",
    "security",
    "test_data",
]
