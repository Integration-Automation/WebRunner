"""Static translator: common Selenium API calls -> Playwright equivalents."""
from je_web_runner.utils.sel_to_pw.translator import (
    SelToPwError,
    Translation,
    translate_action_list,
    translate_python_source,
)

__all__ = [
    "SelToPwError",
    "Translation",
    "translate_action_list",
    "translate_python_source",
]
