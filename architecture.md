# WebRunner Architecture

> Short overview for people and agents.
> Last verified: 2026-10-01 against `25bc167` on `dev`.

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
| `je_web_runner/api/` | Thematic re-export facade (`accessibility_i18n`, `ai`, `api_testing`, `audit`, `authoring`, `debugging`, `diagnostics`, `frontend`, `governance`, `infra`, `messaging`, `mobile`, `mobile_pwa`, `networking`, `observability`, `orchestration`, `performance`, `platform`, `quality`, `reliability`, `security`, `test_data`, `tooling`, `web_platform`); every `utils` subpackage outside the core engine is in exactly one theme (`test/unit_test/test_api_facade.py` fails otherwise); no logic of its own. |
| `je_web_runner/webdriver/` | `webdriver_wrapper.py` (`WebDriverWrapper`, singleton `webdriver_wrapper_instance`) composed from `_wrapper_mixins/` (actions, cookies, media, navigation, scripting, parity: JSON waits / raw selectors / dialogs / CDP emulation; the Selenium event capture, HAR and response mocks live in `utils/bidi/selenium_events.py`, over W3C BiDi); `webdriver_with_options.py`; Playwright backend `playwright_wrapper.py` (`PlaywrightWrapper`: launch, context, quit, plus the `pw_*` module functions) composed from `_playwright_mixins/` (context, page, interaction, state, recording, scope: current frame / user-facing lookup / dialogs, connect: CDP attach / browser server / persistent profile, sessions: several browsers switched by index), `playwright_element_wrapper.py`, `playwright_locator.py`. |
| `je_web_runner/element/` | `web_element_wrapper.py`: operations on the currently selected Selenium element. |
| `je_web_runner/manager/` | `webrunner_manager.py`: `WebdriverManager` (singleton `web_runner`) for multiple live drivers. |
| `je_web_runner/utils/executor/` | `action_executor.py`: `Executor`, a `je_action_core.ActionExecutor` (WebRunner's action parser and list rules, command gate, retry and span through `attempt`, failure screenshots in the failure record), and the `executor` singleton; its `event_dict` is built by `_event_table.build_event_dict()` from `COMMANDS` plus `_playwright_commands.PLAYWRIGHT_COMMANDS`. |
| `je_web_runner/mcp_server/` | MCP stdio server: `McpServer` and per-request era routing (`server.py`), versions and identity (`_protocol.py`), the stateless 2026-07-28 revision (`_stateless.py`), `Tool` / `ToolResult` / errors (`_types.py`), offline tools (`offline_tools.py`, `build_default_tools()`), live-browser tools (`browser_tools.py`) and the caller policy (`_policy.py`). |
| `je_web_runner/action_lsp/` | Language server for action JSON files. |
| `je_web_runner/utils/` | One flat level of subpackages; functional areas below. |
| `test/` | `unit_test/` (mock-based), `integration_test/` (real I/O, MCP / LSP / CLI subprocesses), `e2e_test/` (Selenium Grid). |
| `docs/` | Sphinx sources (`docs/source/Eng`, `Zh`, `API`; longer architecture chapter in `docs/source/Eng/doc/architecture/architecture_doc.rst`), generated `docs/reference/command_reference.md` and `webrunner-action-schema.json`, IDE samples in `docs/ide/`. |
| `examples/`, `docker/`, `web_runner_driver/` | Example scripts and action files, Selenium Grid compose file for e2e, driver build script. |

**`utils/` functional areas** (examples, not exhaustive; `docs/reference/utils_index.md` lists every subpackage by layer):

| Area | Example subpackages |
| --- | --- |
| Core engine and action I/O | `executor`, `callback`, `package_manager`, `json`, `test_object`, `test_record`, `exception`, `logging`, `file_process`, `xml` |
| Run orchestration and CI | `async_executor` (asyncio engine, `WR_apw_*`), `cli`, `socket_server`, `watch_mode`, `scheduler`, `sharding`, `test_filter`, `run_ledger`, `pipeline`, `k8s_runner`, `fanout`, `multi_user`, `ab_run` |
| Browser and driver control | `cdp`, `cdp_tap`, `bidi`, `bidi_backend`, `driver_dispatch`, `chrome_profile`, `browser_pool`, `process_supervisor`, `driver_pin`, `cloud_grid`, `device_cloud`, `appium_integration`, `dom_traversal`, `storage`, `network_emulation`, `smart_wait`, `autocontrol_bridge` (desktop control through AutoControl) |
| Authoring and code generation | `recorder`, `action_formatter`, `action_templates`, `md_authoring`, `linter`, `schema`, `docs`, `pom_generator`, `sel_to_pw`, `session_to_test`, `openapi_to_e2e`, `project` |
| Reporting and observability | `generate_report`, `observability`, `otel_bridge`, `trace_recorder`, `failure_bundle`, `replay_studio`, `dashboard`, `live_dashboard`, `notifier`, `ci_annotations`, `test_management` |
| Reliability, flakes and test governance | `adaptive_retry`, `self_healing`, `flake_detector`, `flakiness_graveyard`, `repro_minimizer`, `failure_triage`, `failure_cluster`, `locator_health`, `mutation_testing`, `impact_analysis`, `coverage_map`, `pr_risk_score`, `test_owners_map` |
| API, backend and test data | `api`, `api_mock`, `contract_testing`, `graphql`, `grpc_tester`, `har_replay`, `mock_services`, `webhook_receiver`, `database`, `db_snapshot`, `testcontainers_integration`, `data_driven`, `env_config`, `factories`, `auth`, `otp_interceptor`, `download_verify` |
| Web-platform API assertions and mocks | `websocket_assert`, `sse_assert`, `webrtc_assert`, `webauthn_mock`, `webusb_mock`, `web_locks`, `view_transitions`, `indexed_db_explorer`, `cross_tab_sync`, `touch_gesture`, `time_freezer` |
| Performance budgets | `web_vitals` (`WR_assert_web_vitals` over `perf_metrics`, `inp_tracker` and `lighthouse`), `perf_metrics`, `perf_drift`, `lighthouse`, `lighthouse_regression`, `inp_tracker`, `bundle_budget`, `third_party_budget`, `memory_leak`, `load_test` |
| Security and privacy | `security_headers`, `secrets_scanner`, `csp_reporter`, `dom_xss_taint`, `tls_cipher_audit`, `cors_matrix`, `pii_scanner`, `token_leak_detector`, `consent_audit`, `sbom_diff`, `license_scanner` |
| Accessibility, i18n and visual | `accessibility`, `a11y_trend`, `screen_reader_runner`, `wcag22_touch_target`, `pseudo_localization`, `rtl_layout_verify`, `visual_regression`, `visual_ai`, `visual_review`, `snapshot`, `ocr_assert` |
| Language-model hooks and LLM-feature checks | `ai_assist`, `test_auto_repair`, `failure_narrator`, `exploratory_ai`, `multimodal_qa`, `edge_case_generator`, `rag_grounding_assert`, `hallucination_probe`, `prompt_injection_scanner` |

## 3. Entry points and public interfaces

| Surface | Exact name | Notes |
| --- | --- | --- |
| Python facade | `import je_web_runner` | `webdriver_wrapper_instance`, `web_element_wrapper`, `get_webdriver_manager`, `execute_action`, `execute_one`, `execute_files`, `executor`, `add_command_to_executor`, `TestObject`, `test_record_instance`, report generators, `playwright_wrapper_instance`, `pw_*`. |
| Thematic facade | `je_web_runner.api.<theme>` | Same objects as `je_web_runner.utils.<area>`, grouped for discovery. |
| CLI | `python -m je_web_runner` and the console scripts `webrunner` / `web_runner` → `__main__.py:run` → `utils/cli/cli_main.py:main` | `run` prints an escaping error as one `repr` line on stderr and exits 1. Legacy flags: `-e/--execute_file FILE`, `-d/--execute_dir DIR`, `--execute_str JSON` (double-encoded JSON accepted on Windows). Newer: `--validate`, `--validate_dir`, `--parallel N`, `--parallel-mode thread\|process\|async`, `--report BASE`, `--tag`, `--exclude-tag`, `--ledger`, `--rerun-failed`, `--watch`, `--migrate`, `--migrate-dry-run`, `--shard I/N`, `--affected-by KIND:VALUE`, `--changed-since REF`, `--impact-cache PATH` (impact selection: `utils/impact_analysis/selection.py`). There is no `-c` flag; scaffolding is `create_project_dir()`. |
| MCP server | `python -m je_web_runner.mcp_server` → `serve_stdio()` | Newline-delimited JSON-RPC over stdio; `build_default_tools()` (offline tools) + `build_browser_tools()` (`webrunner_run_actions`, `webrunner_run_action_files`, `webrunner_list_commands`). |
| LSP | `python -m je_web_runner.action_lsp` → `action_lsp/server.py:serve_stdio` | Completion from `executor.event_dict`; diagnostics from the action linter. |
| TCP server | `start_web_runner_socket_server()` in `utils/socket_server/web_runner_socket_server.py` | Default `localhost:9941`, optional `auth_token` and TLS; client helpers `send_command`, `read_frame`, `encode_frame`. |
| HTTP dashboards | `utils/dashboard/live_dashboard.py` (per-run progress), `utils/live_dashboard/server.py` (`DashboardServer`: routes; `_data.py` loaders, `_pages.py` pages, `_widgets.py` escaping HTML helpers, `_charts.py` SVG, `_assets.py` stylesheet / script / icon, `_config.py`) | Local progress and summary views; there is no general REST API. |
| PyPI packages | `je_web_runner` (stable), `je_web_runner_dev` (dev channel) | Stable: a push to `main` runs `publish_stable.yml`, which bumps `pyproject.toml`, tags and uploads. Dev: the `publish-dev` job of `test_dev.yml` runs after the tests on a push to `dev`, builds from `dev.toml` and uploads when the commit is still the tip of `dev` and the wheel differs from the newest published one; `scripts/dev_release.py` takes the version from PyPI (newest release plus one patch), so nothing is committed back. Both jobs install only the hash-locked `.github/requirements/publish.txt` and build with `python -m build --no-isolation`, so the build backend is the locked `setuptools` too. |
| pytest plugin, GUI | none | GUI access is provided by consumers (AutoControlGUI `gui/webrunner_tab.py`, PyBreeze menus). |

## 4. Main flows

**A. Action JSON → browser (primary path)**

```
action file → utils/json/json_file/json_file.read_action_json
  → Executor.execute_action              (je_action_core's loop; logs the list, then action_list_of: dict input must carry "webdriver_wrapper")
  → attempt → _execute_with_retry        (optional span factory, global retry policy)
  → _execute_event                       (refused commands and the arbitrary-script gate → _ActionParser.bind looks up event_dict[cmd]; shapes [cmd] | [cmd, {kw}] | [cmd, [args]] | [cmd, [args], {kw}])
  → webdriver_wrapper_instance / web_element_wrapper / web_runner (WebdriverManager) | playwright_wrapper (WR_pw_*)
  → Selenium / Playwright; wrappers append to test_record_instance
  → result dict {"execute: [...]": return value or the error text}; a repeated key gets " #2" …; each entry is also printed to stdout
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
   `webdriver/_wrapper_mixins/_*_mixin.py`, `element/web_element_wrapper.py` or
   `webdriver/_playwright_mixins/_*_mixin.py` (with a `pw_*` function in `webdriver/playwright_wrapper.py`).
2. Register `"WR_<name>"` in the command table: `COMMANDS` in `utils/executor/_event_table.py`, or
   `PLAYWRIGHT_COMMANDS` in `utils/executor/_playwright_commands.py` for `WR_pw_*`. Add aliases instead of
   renaming existing names. Commands that ship JS or CDP strings to the browser also go into `_ARBITRARY_SCRIPT_COMMANDS`.
3. If callbacks must reach it, add it to the separate `event_dict` in `utils/callback/callback_function_executor.py`.
4. For a Python-level public name, re-export it in `je_web_runner/__init__.py` (`__all__`) and/or the matching
   `je_web_runner/api/<theme>.py`. A new `utils` subpackage must go into one theme.
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
| Jeffrey_RPA | `JeffreyRPA/webrunner_je_only.py` and `webrunner_novelai.py` insert a WebRunner working tree at `sys.path[0]`, so the **live working tree** is imported. The tree is `WEBRUNNER_PATH`, else `bot_config.json` `webrunner_path`, else the sibling `D:\Codes\WebRunner`, else the installed package (one rule, `JeffreyRPA/_webrunner_location.py`). Before importing it sets `WEBRUNNER_LOG_PATH` (if unset) to its own `webrunner.log`; `Jeffrey_RPA/requirements.txt` requires `je_web_runner>=0.0.88` because of the four wrapper methods listed here. | `TestObject`, `webdriver_wrapper_instance` and its methods `get_current_url`, `get_title`, `save_screenshot`, `add_script_to_evaluate_on_new_document`; for its je_web_runner variant, `set_driver(..., install_driver=False)` (start without webdriver-manager) and `executor.set_raise_wrapper_errors`; `test/test_je_facade.py` (in Jeffrey_RPA) imports `je_web_runner.webdriver.webdriver_wrapper` and checks `_webdriver_dict`. |
| Jeffrey_RPA tests | `JeffreyRPA/conftest.py` hooks the import of `je_web_runner.utils.logging.loggin_instance` to park the log file outside the repo. | That exact, misspelled module path. **Do not rename it.** |
| AutoControlGUI | Optional `utils/webrunner_bridge/bridge.py` (not a declared dependency; found with `importlib.util.find_spec`, imported lazily). | `je_web_runner.utils.executor.action_executor`: `execute_one` (one action through the gates, raising `WebRunnerExecuteException`), falling back to `executor.event_dict` on releases without it; `executor.event_dict` `WR_*` keys for listing; the commands `WR_get_webdriver_manager`, `WR_to_url`, `WR_quit`, `WR_save_screenshot`, `WR_get_current_url` (guarded by `test/unit_test/test_public_api.py`); `je_web_runner.utils.exception.exceptions.WebRunnerException` as the failure it wraps. |
| TestPioneer | Declared dependency; `from je_web_runner import execute_action` in-process. | `execute_action`. |
| PyBreeze | Subprocess `python -m je_web_runner --execute_str <json>` / `--execute_file <path>`, reading stdout. | Legacy CLI flags, Windows double-encoded `--execute_str`, results printed to stdout; guarded by `test/unit_test/test_legacy_cli_contract.py`. |

**Outbound (required):** `je_action_core>=0.0.3` (PyPI), the executor core shared with APITestka, LoadDensity,
MailThunder and FileAutomation. `utils/executor/action_executor.py` relies on `ActionExecutor` (its loop,
`attempt`, `_execute_event`, `collect_action_results`, `execute_files`, `add_command_to_executor`), `ExecutorSettings`
(`rules` as any object with `extract`, `parser`, `reporter`, `read_json`, `failure_record`, `duplicate_keys`
`DuplicateKeys.NUMBER`), `BoundAction`, `PrintReporter` (with `on_start`), `CommandRegistry` with
`CommandPolicy.FUNCTIONS_ONLY`, and `SAFE_BUILTINS` / `safe_builtin_commands` / `unique_record_key` (the last two
names are re-exported from `action_executor`). ActionCore lists WebRunner in its own §6. An interpreter that
imports a working tree through `sys.path` (Jeffrey_RPA) needs it installed: that import installs no dependencies.

**Outbound (optional):** `utils/autocontrol_bridge/` (`WR_ac_*`) runs AutoControlGUI's `je_auto_control`, an optional
extra (`je_web_runner[autocontrol]`) that is never imported at import time: importing `je_auto_control` makes the
process DPI-aware on Windows and takes about a second, and Jeffrey_RPA imports this tree. `ac_available` uses
`importlib.util.find_spec`. It relies on `je_auto_control.utils.executor.action_executor.executor` with
`execute_action(actions, raise_on_error=True)` (a record dict, one unique key per action, in order) and
`known_commands()`, and on the `AC_*` commands the native ones send: `AC_write` (`write_string`), `AC_write_secret`
(`secret`; `WR_ac_basic_auth` checks `known_commands()` for it and refuses without it, and skips the deny scan for
the actions it builds, so a password is never echoed in a refusal),
`AC_type_keyboard` (`keycode`), `AC_get_keyboard_keys_table` (its `enter` or `return` key) and
`AC_locate_image_center` (`image`, `detect_threshold`; returns the centre, raises when not found) and
`AC_click_mouse` (`mouse_keycode`, `x`, `y` in the coordinates of a DPI-aware process; `screen_mapping.py` maps a
page point to them). It refuses
`AC_shell_command`,
`AC_execute_process`, `AC_add_package_*`, `AC_execute_action`, `AC_execute_files`, `AC_run_agent` and `AC_web_*`
anywhere in an action. `test/integration_test/test_autocontrol_bridge_real.py` checks these against the installed
package and skips without it.

**Public promise (README):** the top-level `webdriver_wrapper_instance`, `execute_action`, `TestObject` and the
original CLI entry points (`-e`, `-d`, `--execute_str`) stay unchanged; README › Advanced WebDriverWrapper also keeps
`WebDriverWrapper` and the `_options_dict` / `_webdriver_dict` / `_webdriver_manager_dict` patch targets stable.

**Supported module paths (public, README › Public API & Deprecation Policy):**
`utils/executor/action_executor.py` (`executor`, `execute_one`), `utils/logging/loggin_instance.py`
(`web_runner_logger`, also exported top-level since 0.0.90, and `WebRunnerLoggingHandler`),
`webdriver/webdriver_wrapper.py`. Moves or renames are breaking changes and follow the deprecation
policy; `test/unit_test/test_public_api.py` guards them.

**Import-time side effects:** `utils/logging/loggin_instance.py` sets the root logger to DEBUG and attaches a
handler that opens nothing until the first record. The file is `$WEBRUNNER_LOG_PATH`, else
`$WEBRUNNER_LOG_DIR/WEBRunner.log`, else `~/.je_web_runner/logs/WEBRunner.log` (append, process id per line).
Jeffrey_RPA points `WEBRUNNER_LOG_PATH` at its own `webrunner.log`, which its supervisor also writes.
`webdriver_wrapper_instance`, `web_runner` and `executor` are module-level singletons: concurrent callers in one
process share one driver (`--parallel-mode process` exists for isolation).

## 7. Design constraints

- Executor calls only registered commands: the `WR_*` table plus the 22-name `SAFE_BUILTINS` allowlist
  (`abs` … `sum`), the same list MailThunder and LoadDensity use; nothing else reaches `event_dict`
  (workspace `progress.md` X-12). → CLAUDE.md › Coding Standards › Security Requirements
- `WR_add_package_to_executor` / `WR_add_package_to_callback_executor` pass the package gate in
  `utils/package_manager/package_manager_class.py` before importing: `executor.allow_packages(...)` and
  `executor.set_allow_arbitrary_packages(...)` are Python-only, never `WR_*` commands, so an action file cannot open
  its own gate. Unconfigured, any package loads with a `DeprecationWarning` (progress #22 flips the default).
- MCP calls run inside `executor.restricted(...)`, which refuses the package-loading commands and
  `WR_set_allow_arbitrary_script` in nested action lists too (`mcp_server/_policy.py`;
  `WEBRUNNER_MCP_ALLOW_UNSAFE_COMMANDS=1` lifts it, `WEBRUNNER_MCP_ROOT` fences the file tools).
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
