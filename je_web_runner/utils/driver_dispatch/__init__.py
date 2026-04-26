"""Shared Selenium / Playwright JS execution dispatch."""
from je_web_runner.utils.driver_dispatch.js_eval import (
    DriverDispatchError,
    evaluate_expression,
    run_script,
)

__all__ = ["DriverDispatchError", "evaluate_expression", "run_script"]
