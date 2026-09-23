# WebRunner Architecture

> Short overview for people and agents.
> Last verified: 2026-09-22 against `4566857` on `dev`.

## 1. Purpose

WebRunner (`je_web_runner`) is a web automation and testing framework built on Selenium, with an opt-in
Playwright backend. Browser actions, assertions, reports and test orchestration are driven either from Python or
from JSON action files whose `WR_*` command names resolve through one executor. Around that core, `utils/` holds
a wide set of self-contained testing helpers (API, security, performance, accessibility, flake management and more).

## 2. Layers and directories

Layering: entry points (CLI, TCP, MCP, LSP, Python) → `utils/executor/` (`WR_*` dispatch) → wrappers in
`webdriver/`, `element/`, `manager/` → Selenium / Playwright. Most `utils/` subpackages are leaf libraries: some are
wired into the executor as `WR_*` commands, others are reachable only from Python.

| Path | Responsibility |
| --- | --- |
| `je_web_runner/__init__.py` | Facade: the original Selenium-flavoured public API plus selected helpers, listed in `__all__`. |
| `je_web_runner/api/` | Thematic re-export facade (`authoring`, `debugging`, `frontend`, `infra`, `mobile`, `networking`, `observability`, `quality`, `reliability`, `security`, `test_data`); no logic of its own. |
| `je_web_runner/webdriver/` | `webdriver_wrapper.py` (`WebDriverWrapper`, singleton `webdriver_wrapper_instance`) composed from `_wrapper_mixins/` (actions, cookies, media, navigation, scripting); `webdriver_with_options.py`; Playwright backend `playwright_wrapper.py`, `playwright_element_wrapper.py`, `playwright_locator.py`. |
| `je_web_runner/element/` | `web_element_wrapper.py`: operations on the currently selected Selenium element. |
| `je_web_runner/manager/` | `webrunner_manager.py`: `WebdriverManager` (singleton `web_runner`) for multiple live drivers. |
| `je_web_runner/mcp_server/` | MCP stdio server (`server.py`) and live-browser tools (`browser_tools.py`). |
| `je_web_runner/action_lsp/` | Language server for action JSON files. |
| `je_web_runner/utils/` | One flat level of subpackages; functional areas below. |
| `test/` | `unit_test/` (mock-based), `integration_test/` (real I/O, MCP / LSP / CLI subprocesses), `e2e_test/` (Selenium Grid). |
| `docs/` | Sphinx sources (`docs/source/Eng`, `Zh`, `API`; longer architecture chapter in `docs/source/Eng/doc/architecture/architecture_doc.rst`), generated `docs/reference/command_reference.md` and `webrunner-action-schema.json`, IDE samples in `docs/ide/`. |
| `examples/`, `docker/`, `web_runner_driver/` | Example scripts and action files, Selenium Grid compose file for e2e, driver build script. |

**`utils/` functional areas** (examples, not exhaustive; `README.md` › Module map lists more):

| Area | Example subpackages |
| --- | --- |
| Core engine and action I/O | `executor`, `callback`, `package_manager`, `json`, `test_object`, `test_record`, `exception`, `logging`, `file_process`, `xml` |
| Run orchestration and CI | `cli`, `socket_server`, `watch_mode`, `scheduler`, `sharding`, `test_filter`, `run_ledger`, `pipeline`, `k8s_runner`, `fanout`, `multi_user`, `ab_run` |
| Browser and driver control | `cdp`, `cdp_tap`, `bidi`, `bidi_backend`, `driver_dispatch`, `chrome_profile`, `browser_pool`, `process_supervisor`, `driver_pin`, `cloud_grid`, `device_cloud`, `appium_integration`, `dom_traversal`, `storage`, `network_emulation`, `smart_wait` |
| Authoring and code generation | `recorder`, `action_formatter`, `action_templates`, `md_authoring`, `linter`, `schema`, `docs`, `pom_generator`, `sel_to_pw`, `session_to_test`, `openapi_to_e2e`, `project` |
| Reporting and observability | `generate_report`, `observability`, `otel_bridge`, `trace_recorder`, `failure_bundle`, `replay_studio`, `dashboard`, `live_dashboard`, `notifier`, `ci_annotations`, `test_management` |
| Reliability, flakes and test governance | `adaptive_retry`, `self_healing`, `flake_detector`, `flakiness_graveyard`, `repro_minimizer`, `failure_triage`, `failure_cluster`, `locator_health`, `mutation_testing`, `impact_analysis`, `coverage_map`, `pr_risk_score`, `test_owners_map` |
| API, backend and test data | `api`, `api_mock`, `contract_testing`, `graphql`, `grpc_tester`, `har_replay`, `mock_services`, `webhook_receiver`, `database`, `db_snapshot`, `testcontainers_integration`, `data_driven`, `env_config`, `factories`, `auth`, `otp_interceptor`, `download_verify` |
| Web-platform API assertions and mocks | `websocket_assert`, `sse_assert`, `webrtc_assert`, `webauthn_mock`, `webusb_mock`, `web_locks`, `view_transitions`, `indexed_db_explorer`, `cross_tab_sync`, `touch_gesture`, `time_freezer` |
| Performance budgets | `perf_metrics`, `perf_drift`, `lighthouse`, `lighthouse_regression`, `inp_tracker`, `bundle_budget`, `third_party_budget`, `memory_leak`, `load_test` |
| Security and privacy | `security_headers`, `secrets_scanner`, `csp_reporter`, `dom_xss_taint`, `tls_cipher_audit`, `cors_matrix`, `pii_scanner`, `token_leak_detector`, `consent_audit`, `sbom_diff`, `license_scanner` |
| Accessibility, i18n and visual | `accessibility`, `a11y_trend`, `screen_reader_runner`, `wcag22_touch_target`, `pseudo_localization`, `rtl_layout_verify`, `visual_regression`, `visual_ai`, `visual_review`, `snapshot`, `ocr_assert` |
| Language-model hooks and LLM-feature checks | `ai_assist`, `test_auto_repair`, `failure_narrator`, `exploratory_ai`, `multimodal_qa`, `edge_case_generator`, `rag_grounding_assert`, `hallucination_probe`, `prompt_injection_scanner` |

## 3. Entry points and public interfaces

| Surface | Exact name | Notes |
| --- | --- | --- |
| Python facade | `import je_web_runner` | `webdriver_wrapper_instance`, `web_element_wrapper`, `get_webdriver_manager`, `execute_action`, `execute_files`, `executor`, `add_command_to_executor`, `TestObject`, `test_record_instance`, report generators, `playwright_wrapper_instance`, `pw_*`. |
| Thematic facade | `je_web_runner.api.<theme>` | Same objects as `je_web_runner.utils.<area>`, grouped for discovery. |
| CLI | `python -m je_web_runner` → `utils/cli/cli_main.py:main` | No console script is declared in `pyproject.toml`. Legacy flags: `-e/--execute_file FILE`, `-d/--execute_dir DIR`, `--execute_str JSON` (double-encoded JSON accepted on Windows). Newer: `--validate`, `--validate_dir`, `--parallel N`, `--parallel-mode thread\|process`, `--report BASE`, `--tag`, `--exclude-tag`, `--ledger`, `--rerun-failed`, `--watch`, `--migrate`, `--migrate-dry-run`, `--shard I/N`. There is no `-c` flag; scaffolding is `create_project_dir()`. |
| MCP server | `python -m je_web_runner.mcp_server` → `serve_stdio()` | Newline-delimited JSON-RPC over stdio; `build_default_tools()` (offline tools) + `build_browser_tools()` (`webrunner_run_actions`, `webrunner_run_action_files`, `webrunner_list_commands`). |
| LSP | `python -m je_web_runner.action_lsp` → `action_lsp/server.py:serve_stdio` | Completion from `executor.event_dict`; diagnostics from the action linter. |
| TCP server | `start_web_runner_socket_server()` in `utils/socket_server/web_runner_socket_server.py` | Default `localhost:9941`, optional `auth_token` and TLS; client helpers `send_command`, `read_frame`, `encode_frame`. |
| HTTP dashboards | `utils/dashboard/live_dashboard.py`, `utils/live_dashboard/server.py` (`DashboardServer`) | Local progress and summary views; there is no general REST API. |
| pytest plugin, GUI | none | GUI access is provided by consumers (AutoControlGUI `gui/webrunner_tab.py`, PyBreeze menus). |

## 4. Main flows

**A. Action JSON → browser (primary path)**

```
action file → utils/json/json_file/json_file.read_action_json
  → Executor.execute_action              (utils/executor/action_executor.py; dict input must carry "webdriver_wrapper")
  → _execute_with_retry                  (optional span factory, global retry policy)
  → _execute_event                       (arbitrary-script gate → event_dict[cmd]; shapes [cmd] | [cmd, {kw}] | [cmd, [args]] | [cmd, [args], {kw}])
  → webdriver_wrapper_instance / web_element_wrapper / web_runner (WebdriverManager) | playwright_wrapper (WR_pw_*)
  → Selenium / Playwright; wrappers append to test_record_instance
  → result dict {"execute: [...]": return value or repr(error)}; each entry is also printed to stdout
```

A failing action is logged and recorded (with an optional auto-screenshot path), and the loop continues.

**B. Directory run from the CLI**

```
python -m je_web_runner -d DIR [--tag/--exclude-tag] [--rerun-failed LEDGER] [--shard I/N]
  → cli_main._select_files → dependency graph (meta.depends_on) → sequential | thread pool | process pool
  → flow A per file → utils/run_ledger/ledger.record_run (optional)
  → --report: JSON + HTML + XML + JUnit reports built from test_record_instance
```

**C. External drivers** (TCP `socket_server`, MCP `browser_tools`, AutoControlGUI bridge, TestPioneer) all call
`execute_action` / `event_dict` on the same module-level `executor`, so they share one browser singleton per process.

## 5. Extension points

**New `WR_*` command**, in order:

1. Implement it in `je_web_runner/utils/<area>/` (new subpackage with `__init__.py`), or as a method on a
   `webdriver/_wrapper_mixins/_*_mixin.py`, `element/web_element_wrapper.py` or `webdriver/playwright_wrapper.py`.
2. Register `"WR_<name>"` in `Executor.event_dict` in `utils/executor/action_executor.py`. Add aliases instead of
   renaming existing names. Commands that ship JS or CDP strings to the browser also go into `_ARBITRARY_SCRIPT_COMMANDS`.
3. If callbacks must reach it, add it to the separate `event_dict` in `utils/callback/callback_function_executor.py`.
4. For a Python-level public name, re-export it in `je_web_runner/__init__.py` (`__all__`) and/or the matching
   `je_web_runner/api/<theme>.py`.
5. Regenerate `docs/reference/command_reference.md` (`export_command_reference`, `utils/docs/command_reference.py`) and
   `docs/reference/webrunner-action-schema.json` (`export_schema`, `utils/schema/action_schema.py`).
6. Add `test/unit_test/test_*.py`; add `test/integration_test/` coverage when several modules are wired together.

**Other seams**

- Runtime commands: `add_command_to_executor({"name": fn})`, or `WR_add_package_to_executor` /
  `WR_add_package_to_callback_executor` (`utils/package_manager/package_manager_class.py`).
- MCP tools: add to `build_default_tools()` (`mcp_server/server.py`) or `build_browser_tools()` (`mcp_server/browser_tools.py`);
  embedders can `McpServer.register(Tool(...))`.
- Report format: new generator in `utils/generate_report/`, added to `expected_paths` / `generate_all_reports` in
  `report_manifest.py` (and to `_generate_reports` in `utils/cli/cli_main.py` if `--report` should emit it).
- Second backend pattern: a wrapper module under `webdriver/` plus prefixed `WR_*` registrations, as Playwright does with `WR_pw_*`.

## 6. Cross-project boundaries

| Consumer | How it uses this repo | What it relies on |
| --- | --- | --- |
| Jeffrey_RPA | `JeffreyRPA/webrunner_je_only.py` and `webrunner_novelai.py` insert `D:\Codes\WebRunner` (or `WEBRUNNER_PATH`) at `sys.path[0]`, so the **live working tree** is imported; `Jeffrey_RPA/requirements.txt` requires `je_web_runner>=0.0.88` because of the four wrapper methods listed here. | `TestObject`, `webdriver_wrapper_instance` and its methods `get_current_url`, `get_title`, `save_screenshot`, `add_script_to_evaluate_on_new_document`; `JeffreyRPA/test_je_facade.py` imports `je_web_runner.webdriver.webdriver_wrapper` and checks `_webdriver_dict`. |
| Jeffrey_RPA tests | `JeffreyRPA/conftest.py` hooks the import of `je_web_runner.utils.logging.loggin_instance` to park the log file outside the repo. | That exact, misspelled module path. **Do not rename it.** |
| AutoControlGUI | Optional `utils/webrunner_bridge/bridge.py` (not a declared dependency). | Internal `je_web_runner.utils.executor.action_executor.executor` and its `event_dict` `WR_*` keys. |
| TestPioneer | Declared dependency; `from je_web_runner import execute_action` in-process. | `execute_action`. |
| PyBreeze | Subprocess `python -m je_web_runner --execute_str <json>` / `--execute_file <path>`, reading stdout. | Legacy CLI flags, Windows double-encoded `--execute_str`, results printed to stdout; guarded by `test/unit_test/test_legacy_cli_contract.py`. |

**Public promise (README):** the top-level `webdriver_wrapper_instance`, `execute_action`, `TestObject` and the
original CLI entry points (`-e`, `-d`, `--execute_str`) stay unchanged; README › Advanced WebDriverWrapper also keeps
`WebDriverWrapper` and the `_options_dict` / `_webdriver_dict` / `_webdriver_manager_dict` patch targets stable.

**Supported module paths (public, README › Public API & Deprecation Policy):**
`utils/executor/action_executor.py` (`executor`), `utils/logging/loggin_instance.py`
(`web_runner_logger`, also exported top-level since 0.0.90, and `WebRunnerLoggingHandler`),
`webdriver/webdriver_wrapper.py`. Moves or renames are breaking changes and follow the deprecation
policy; `test/unit_test/test_public_api.py` guards them.

**Import-time side effects:** `utils/logging/loggin_instance.py` sets the root logger to DEBUG and attaches a
`RotatingFileHandler` for the **relative** path `WEBRunner.log` (mode `"w"`), so the log lands in the caller's cwd.
`webdriver_wrapper_instance`, `web_runner` and `executor` are module-level singletons: concurrent callers in one
process share one driver (`--parallel-mode process` exists for isolation).

## 7. Design constraints

- Executor calls only registered commands: the `WR_*` table plus the 22-name `SAFE_BUILTINS` allowlist
  (`abs` … `sum`), the same list MailThunder and LoadDensity use; nothing else reaches `event_dict`
  (workspace `progress.md` X-12). → CLAUDE.md › Coding Standards › Security Requirements
- Validate all external input (URLs, action JSON, socket messages, CLI args); prevent path traversal; socket server binds
  localhost unless configured; escape dynamic content in HTML reports; parameterize values passed to JS. → same section
- Credentials are never logged or stored in plaintext; use `python-dotenv`. → same section
- Limits: cyclomatic ≤ 10, cognitive ≤ 15, function ≤ 75 lines, file ≤ 750 lines, parameters ≤ 7, nesting ≤ 4,
  line ≤ 120, no duplicated blocks ≥ 3 lines. → CLAUDE.md › Coding Standards › Static Analysis Compliance › Complexity & Maintainability
- No mutable defaults, bare `except`, silently swallowed exceptions or unclosed resources.
  → CLAUDE.md › Coding Standards › Static Analysis Compliance › Bug Prevention
- No `pickle`, `shell=True`, `assert` for security, hard-coded secrets, MD5/SHA-1 for security, `verify=False`,
  or `random` for tokens; parse XML with `defusedxml`. → CLAUDE.md › Coding Standards › Static Analysis Compliance › Security
- Docstrings and type hints on public API; no `TODO` without an issue link.
  → CLAUDE.md › Coding Standards › Static Analysis Compliance › Documentation & Typing
- Waits instead of `time.sleep()`; reuse drivers through the manager. → CLAUDE.md › Coding Standards › Performance Best Practices
- Remove dead code; log at WARNING+ through the rotating handler (`WEBRunner.log`). → CLAUDE.md › Coding Standards › Code Quality
- Run pylint, flake8, bandit, mypy and pytest before committing. → CLAUDE.md › Coding Standards › Pre-Commit Verification
- Tests are `test_*.py` (`pyproject.toml` pins `python_files` because legacy `*_test.py` scripts exit at import);
  every test asserts something; skips carry a reason. → CLAUDE.md › Testing; › Static Analysis Compliance › Testing Quality
- Branches `main` (stable) / `dev`; PRs go `dev` → `main`; imperative commit messages; attribution rules apply.
  → CLAUDE.md › Git & Commit Conventions

## 8. When to update this file

- A top-level subpackage of `je_web_runner/` is added, removed or renamed, or a `utils/` subpackage does not fit any area in §2.
- An entry point changes: CLI flag, `python -m` module, MCP tool family, LSP, socket server defaults or framing.
- The executor contract changes: action shapes, the `webdriver_wrapper` / `meta` top-level keys, retry, gate or error handling.
- Anything in the §6 promise or de-facto public list changes (top-level names, wrapper methods, `loggin_instance`,
  `action_executor.executor`, the log file name or location).
- A sibling repo starts or stops depending on WebRunner, or changes how it loads it.
- A hard rule in CLAUDE.md is added or changed, or the extension steps in §5 change.
- On every edit, refresh the "Last verified" line.
