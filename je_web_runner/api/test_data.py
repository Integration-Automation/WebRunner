"""Façade: DB fixtures / fixture record / form autofill."""
from je_web_runner.utils.database.fixtures import (
    DbFixtureError,
    load_fixture_file,
    load_into_connection,
    truncate_tables,
    validate_shape,
)
from je_web_runner.utils.form_autofill.autofill import (
    FieldMatch,
    FormAutoFillError,
    classify_field,
    match_fields,
    plan_fill_actions,
)
from je_web_runner.utils.snapshot.fixture_record import (
    FixtureRecorder,
    FixtureRecorderError,
    RecorderMode,
    open_recorder,
)

__all__ = [
    "DbFixtureError",
    "load_fixture_file", "load_into_connection",
    "truncate_tables", "validate_shape",
    "FieldMatch", "FormAutoFillError",
    "classify_field", "match_fields", "plan_fill_actions",
    "FixtureRecorder", "FixtureRecorderError",
    "RecorderMode", "open_recorder",
]
