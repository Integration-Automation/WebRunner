"""Facade: Run matrices and test data: A/B, personas, users, flags, chaos, data-driven, DB, env."""
from je_web_runner.utils.ab_run.ab_runner import (
    ABRunError, diff_records, run_ab,
)
from je_web_runner.utils.chaos_hooks.chaos import (
    ChaosHooksError, ChaosFaultType, ChaosEvent, ChaosPlan, plan_chaos, ChaosRunner, run_with_chaos,
)
from je_web_runner.utils.data_driven.data_runner import (
    DataDrivenError, load_dataset_csv, load_dataset_json, expand_with_row, run_with_dataset,
)
from je_web_runner.utils.db_snapshot.snapshot import (
    DbSnapshotError, SnapshotBackend, InMemoryBackend, SnapshotHandle, SnapshotScope, snapshot,
    pytest_fixture_factory, assert_no_active_snapshots,
)
from je_web_runner.utils.env_config.env_loader import (
    EnvConfigError, load_env, get_env, expand_in_action,
)
from je_web_runner.utils.factories.factory import (
    FactoryError, Factory, user_factory, order_factory, product_factory,
)
from je_web_runner.utils.flag_matrix.matrix import (
    FlagMatrixError, FlagSpec, FlagMatrix, build_matrix, forbid, require, ComboResult, MatrixReport,
    summarise_results, smallest_failing_subset,
)
from je_web_runner.utils.multi_user.matrix import (
    MultiUserError, run_for_users,
)
from je_web_runner.utils.persona_runner.runner import (
    PersonaRunnerError, Persona, PersonaCaseResult, MatrixSummary, PersonaCaseRunner, PersonaRunner, summarise,
    summary_markdown,
)
from je_web_runner.utils.test_data.faker_integration import (
    FakerError, seed_faker, reset_faker, fake_value, fake_email, fake_name, fake_first_name, fake_last_name,
    fake_phone, fake_address, fake_uuid, fake_credit_card, fake_url, fake_user_agent, fake_password, fake_text,
)
from je_web_runner.utils.testcontainers_integration.containers import (
    TestcontainersError, start_postgres, start_redis, start_generic, stop_container, cleanup_all, started_count,
)

__all__ = [
    "ABRunError", "diff_records", "run_ab", "ChaosHooksError", "ChaosFaultType", "ChaosEvent", "ChaosPlan",
    "plan_chaos", "ChaosRunner", "run_with_chaos", "DataDrivenError", "load_dataset_csv", "load_dataset_json",
    "expand_with_row", "run_with_dataset", "DbSnapshotError", "SnapshotBackend", "InMemoryBackend",
    "SnapshotHandle", "SnapshotScope", "snapshot", "pytest_fixture_factory", "assert_no_active_snapshots",
    "EnvConfigError", "load_env", "get_env", "expand_in_action", "FactoryError", "Factory", "user_factory",
    "order_factory", "product_factory", "FlagMatrixError", "FlagSpec", "FlagMatrix", "build_matrix", "forbid",
    "require", "ComboResult", "MatrixReport", "summarise_results", "smallest_failing_subset", "MultiUserError",
    "run_for_users", "PersonaRunnerError", "Persona", "PersonaCaseResult", "MatrixSummary", "PersonaCaseRunner",
    "PersonaRunner", "summarise", "summary_markdown", "FakerError", "seed_faker", "reset_faker", "fake_value",
    "fake_email", "fake_name", "fake_first_name", "fake_last_name", "fake_phone", "fake_address", "fake_uuid",
    "fake_credit_card", "fake_url", "fake_user_agent", "fake_password", "fake_text", "TestcontainersError",
    "start_postgres", "start_redis", "start_generic", "stop_container", "cleanup_all", "started_count",
]
