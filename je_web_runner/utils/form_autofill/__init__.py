"""Heuristic form auto-filler: match fields by label/placeholder/name."""
from je_web_runner.utils.form_autofill.autofill import (
    FieldMatch,
    FormAutoFillError,
    classify_field,
    match_fields,
    plan_fill_actions,
)

__all__ = [
    "FieldMatch",
    "FormAutoFillError",
    "classify_field",
    "match_fields",
    "plan_fill_actions",
]
