"""Generate Python Page Object modules from a live DOM snapshot."""
from je_web_runner.utils.pom_codegen.codegen import (
    DiscoveredElement,
    PomCodegenError,
    discover_elements_from_html,
    render_pom_module,
)

__all__ = [
    "DiscoveredElement",
    "PomCodegenError",
    "discover_elements_from_html",
    "render_pom_module",
]
