"""
Thematic façade for the WebRunner extended utilities.

The top-level :mod:`je_web_runner` namespace already exports the original
Selenium-flavoured surface. Every ``je_web_runner.utils`` subpackage outside
the core engine is re-exported by exactly one theme here, so callers can
``from je_web_runner.api import reliability`` rather than memorising deep
import paths; ``docs/reference/utils_index.md`` lists which theme holds which
subpackage.

Each submodule re-exports the public functions and classes of the underlying
``je_web_runner.utils.<X>`` packages without doing any additional logic. A
name two packages of one theme share is prefixed with its package
(``cors_matrix_classify``, ``CookieScopeAbuseSeverity``).

A theme is imported the first time it is used (``from je_web_runner.api import
audit`` or ``je_web_runner.api.audit``), so importing this package loads nothing.
"""
import importlib
from types import ModuleType

__all__ = [
    "accessibility_i18n",
    "ai",
    "api_testing",
    "audit",
    "authoring",
    "debugging",
    "diagnostics",
    "frontend",
    "governance",
    "infra",
    "messaging",
    "mobile",
    "mobile_pwa",
    "networking",
    "observability",
    "orchestration",
    "performance",
    "platform",
    "quality",
    "reliability",
    "security",
    "test_data",
    "tooling",
    "web_platform",
]


def __getattr__(name: str) -> ModuleType:
    """Import a theme on first use (PEP 562)."""
    if name in __all__:
        module = importlib.import_module(f"{__name__}.{name}")
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
