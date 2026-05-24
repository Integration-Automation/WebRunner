# CLAUDE.md — WebRunner

## Project Overview

WebRunner (`je_web_runner`) is a cross-platform web automation framework built on Selenium. It supports multi-browser parallel execution, JSON-driven action scripts, report generation, and remote automation via TCP sockets.

- **Language:** Python 3.10+
- **Dependencies:** selenium, requests, python-dotenv, webdriver-manager
- **Package:** `je_web_runner` (stable) / `je_web_runner_dev` (dev)

## Development Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Install dev dependencies
pip install -r dev_requirements.txt

# Run tests
python -m pytest test/

# Build package
python -m build
```

## Project Structure

```
je_web_runner/
├── __init__.py              # Public API exports
├── __main__.py              # CLI entry point
├── element/                 # WebElement interaction (Wrapper pattern)
├── manager/                 # Multi-driver management (Manager pattern)
├── webdriver/               # WebDriver wrapper & options (Facade pattern)
└── utils/
    ├── callback/            # Event-driven callback executor (Observer pattern)
    ├── exception/           # Custom exception hierarchy
    ├── executor/            # Action executor engine (Command pattern)
    ├── generate_report/     # HTML/JSON/XML report generators (Strategy pattern)
    ├── json/                # JSON file operations
    ├── logging/             # Rotating file handler
    ├── package_manager/     # Dynamic package loading (Plugin pattern)
    ├── project/             # Project template generator (Template pattern)
    ├── socket_server/       # TCP socket server for remote control
    ├── test_object/         # Test object & record classes (Value Object pattern)
    ├── test_record/         # Action recording
    ├── xml/                 # XML utilities
    ├── chrome_profile/      # Persistent Chrome profile + stealth + snapshot/sync-back
    ├── failure_triage/      # AI failure root-cause analysis on failure bundles
    ├── flake_detector/      # Time-decayed flake scoring + quarantine registry
    ├── locator_health/      # Project-wide locator audit + upgrade suggestions
    ├── device_cloud/        # Real-device cloud (BrowserStack/Sauce/LambdaTest) connector
    ├── otel_bridge/         # W3C traceparent injection for distributed tracing
    ├── mutation_testing/    # Action JSON mutation testing (kill rate / score)
    ├── otp_interceptor/     # MailHog/Mailpit/IMAP/SMS OTP polling for 2FA flows
    ├── download_verify/     # PDF / CSV / Excel / JSON / SHA256 download assertions
    ├── test_auto_repair/    # LLM-driven test rewrite from failure + git diff
    ├── edge_case_generator/ # LLM edge-case variant generator (complement to mutation_testing)
    ├── openapi_to_e2e/      # OpenAPI/Swagger spec → WR_http_* action JSON
    ├── cross_tab_sync/      # Multi-page BroadcastChannel / storage propagation asserts
    ├── visual_ai/           # aHash/dHash/pHash + SSIM-proxy for canvas/chart diff
    ├── test_scheduler/      # Value-density scheduler under time + cloud budget
    ├── walkthrough_docs/    # AI step-by-step SOP / Confluence doc from recorded runs
    ├── live_dashboard/      # Aggregated web UI: runs + flake + quarantine + locators
    ├── ocr_assert/          # OCR-based text assertion for canvas / WebGL / image content
    ├── email_render/        # Capture outbound mail (MailHog/Mailpit/EML) + multi-viewport screenshots
    ├── backend_log_correlator/ # W3C trace_id → Loki/Elasticsearch/file log fetch into failure bundle
    ├── websocket_assert/    # WebSocket frame recorder + count / payload / pubsub assertions
    ├── console_error_budget/ # JS console / unhandled-rejection budget with ignore patterns
    ├── chaos_hooks/         # Seeded chaos injection (offline / throttle / mid-flow reload)
    ├── pr_risk_score/       # Fuse flake / impact / locator / coverage signals into 0-100 PR risk
    ├── flag_matrix/         # Feature-flag combo matrix with constraints + minimal failing subset
    ├── session_to_test/     # rrweb / generic session events → WR action JSON
    ├── exploratory_ai/      # Agentic exploratory tester (observer/planner protocols + RandomPlanner)
    ├── story_to_actions/    # LLM-driven user story / Figma frame → validated WR action JSON
    ├── db_snapshot/         # Per-test DB savepoint/rollback with pluggable backend
    ├── time_freezer/        # Inject Date/Date.now/performance.now patch via CDP for deterministic time tests
    ├── persona_runner/      # Same suite × N personas (admin/free/enterprise) matrix
    ├── token_leak_detector/ # Scan HAR / logs / responses for leaked JWTs, API keys, session tokens
    ├── consent_audit/       # GDPR/CCPA cookie classification + pre-consent / post-reject violation detection
    ├── pii_in_screenshot/   # OCR + PII regex (Luhn-validated card, SSN, TWID) scanner over screenshots
    ├── pseudo_localization/ # ASCII → look-alike + expansion + brackets; detect hard-coded i18n leaks
    ├── screen_reader_runner/ # Walk a11y tree to simulate NVDA/VoiceOver order + flag a11y violations
    ├── forced_colors_mode/  # dark / reduced-motion / forced-colors / high-contrast matrix verification
    ├── sse_assert/          # Server-Sent Events recorder + count/data/JSON-shape/strict-id assertions
    ├── webrtc_assert/       # PeerConnection state / ICE / track / RTP stats assertions
    ├── view_transitions/    # Instrumentation + duration/CLS/group assertions for View Transitions API
    ├── test_dedup_ai/       # Structural + embedding-based semantic dedupe of action JSON files
    ├── multimodal_qa/       # Send screenshot + question to vision LLM, parse pass/fail/notes envelope
    ├── prompt_drift_monitor/ # Track LLM-feature output drift via embeddings + lexical anchors
    ├── git_bisect_flake/    # Ledger-only or probe-driven bisect to find regression commit
    ├── test_cost_estimator/ # Cloud-minute × rate-card × CO₂ estimate per suite/runner/test
    ├── slack_digest/        # Render Slack Block-Kit / Teams card / plain-text test digest payload
    ├── webtransport_assert/ # HTTP/3 WebTransport datagram + stream frame recorder + assertions
    ├── indexed_db_explorer/ # IndexedDB snapshot harvest + store/key/index/record assertions
    ├── file_system_access/  # Mock showOpenFilePicker/showSaveFilePicker + record writes
    ├── notifications_audit/ # Notification.requestPermission timing + permission/spam policy checks
    ├── mixed_content_audit/ # HTTP-on-HTTPS detection via HAR + console scanner
    ├── clickjacking_audit/  # X-Frame-Options / frame-ancestors header check + iframe probe
    ├── open_redirect_detector/ # Probe ?redirect=/?next= params with attacker-host payloads
    ├── sri_verify/          # Subresource Integrity hash presence + correctness + crossorigin
    ├── coop_coep_audit/     # crossOriginIsolated COOP/COEP + per-resource CORP/CORS check
    ├── inp_tracker/         # Interaction to Next Paint instrumentation + p98 + budget
    ├── hydration_check/     # SSR hydration mismatch detection (DOM diff + console markers)
    ├── bundle_budget/       # Per-asset-kind byte budget from HAR + biggest-assets ranking
    ├── third_party_budget/  # Third-party vendor classification + req/byte/blocking-ms budgets
    ├── long_animation_frame/ # Long Animation Frame API listener + per-script attribution
    ├── grpc_tester/         # gRPC stub call recorder + gRPC-Web framing/trailer helpers
    ├── webhook_receiver/    # Threaded HTTP server for catching app's outbound webhooks
    ├── idempotency_check/   # Run request twice + compare status/body/state/side-effects
    ├── pagination_audit/    # Walk all pages, detect dups/gaps/cursor-loop/sort violations
    ├── failure_narrator/    # LLM natural-language failure summary from failure_bundle
    ├── repro_minimizer/     # Delta-debugging (ddmin) to shrink failing action list to minimum
    ├── locator_hardener/    # Heuristic fragility score + LLM-suggested stable selectors
    ├── test_categorizer/    # Auto-tag tests as smoke / regression / perf / a11y / data / api
    ├── quarantine_age_report/ # Quarantine entries with age + fresh/lingering/stale/abandoned tiers
    ├── test_debt_dashboard/ # Inventory of skip/xfail/TODO/_skip markers with age + CODEOWNERS
    ├── sla_tracker/         # % suites finishing under SLA threshold, weekly/daily bucketing
    ├── bug_repro_stability/ # Repeat probe N times, classify deterministic/flaky/non-reproducible
    └── test_owners_map/     # CODEOWNERS parser + override layer + unowned-test audit
```

## Design Patterns & Architecture

- **Facade:** `WebDriverWrapper` abstracts Selenium's complex API into a simplified interface
- **Command:** Action executor maps string commands to callable functions, enabling JSON-driven automation
- **Manager:** `WebdriverManager` coordinates multiple browser instances for parallel execution
- **Observer/Callback:** `callback_executor` provides event-driven hooks on action completion
- **Strategy:** Report generators (HTML/JSON/XML) share a common interface with interchangeable output formats
- **Plugin:** `package_manager` dynamically loads external packages into the executor at runtime
- **Value Object:** `TestObject` encapsulates immutable locator information (name + strategy)

## Coding Standards

### Software Engineering Principles

- **SOLID:** Each module has a single responsibility; depend on abstractions (wrappers), not Selenium internals directly
- **DRY:** Reuse existing wrappers and utilities; never duplicate element-finding or driver-management logic
- **KISS:** Prefer clear, readable code over clever abstractions; no premature optimization
- **YAGNI:** Only implement features that are currently needed; no speculative code

### Performance Best Practices

- Use implicit/explicit waits instead of `time.sleep()` for element synchronization
- Prefer `find_element` with specific locators (ID, CSS selector) over slow strategies (XPath with text matching)
- Reuse WebDriver instances via the manager instead of creating new ones
- Minimize JavaScript execution calls; batch operations where possible
- Use connection pooling for socket server communications
- Avoid loading unnecessary browser extensions or capabilities

### Security Requirements

- **Input validation:** Validate and sanitize ALL external inputs — URLs, JSON action files, socket messages, CLI arguments
- **No arbitrary code execution:** Action executor must only call registered commands; never use `eval()` or `exec()` on user input
- **Socket server:** Bind to localhost by default; require explicit configuration for network exposure
- **File operations:** Use safe path handling; prevent path traversal attacks in file-based action execution
- **Credentials:** Never log, store, or transmit credentials in plaintext; use `python-dotenv` for environment-based secrets
- **Dependencies:** Keep all dependencies up to date; audit for known vulnerabilities regularly
- **XSS prevention:** Escape all dynamic content in generated HTML reports
- **Injection prevention:** Parameterize any dynamic values passed to JavaScript execution

### Code Quality

- Remove dead code, unused imports, and commented-out blocks — do not leave them in the codebase
- Every function should have a clear purpose; if it's unused, delete it
- Keep modules focused; extract new modules only when a clear boundary exists
- Type hints on all public API functions
- Logging at WARNING+ level via the rotating file handler (`WEBRunner.log`)

### Static Analysis Compliance (SonarQube & Codacy)

All code MUST pass SonarQube and Codacy static analysis without introducing new issues. Follow these rules proactively:

#### Complexity & Maintainability

- **Cognitive complexity ≤ 15** per function (SonarQube `python:S3776`); extract helpers when nesting grows
- **Cyclomatic complexity ≤ 10** per function; split branchy logic into smaller units
- **Function length ≤ 75 lines**; **file length ≤ 750 lines**; **parameters ≤ 7** per function (`python:S107`)
- **Max nesting depth = 4** (`python:S134`); use early returns / guard clauses to flatten
- **No duplicated code blocks ≥ 3 lines** (`common-py:DuplicatedBlocks`); extract shared logic
- **No dead stores** — never assign a value that is immediately overwritten or unused (`python:S1854`)

#### Naming & Style (PEP 8 enforced)

- Modules / functions / variables: `snake_case`; classes: `PascalCase`; constants: `UPPER_SNAKE_CASE` (`python:S116`, `python:S117`)
- No single-letter names except loop indices `i`, `j`, `k` and comprehension vars
- Line length ≤ 120 chars; 4-space indentation; no tabs
- No wildcard imports (`from x import *`) — `python:S2208`
- One statement per line; no semicolons

#### Bug Prevention

- **Never use mutable default arguments** (`def f(x=[])`) — use `None` and initialize inside (`python:S5797`)
- **Never use bare `except:`** — catch specific exceptions (`python:S5754`); never `except Exception` without re-raise/log
- **Never silently swallow exceptions** — `pass` inside `except` is forbidden unless justified by a `# noqa` comment (`python:S2486`)
- **Always close resources** — use `with` for files, sockets, drivers (`python:S5042`)
- **No `==` comparison with `None`, `True`, `False`** — use `is` / `is not` (`python:S5727`)
- **No identical expressions on both sides** of `==`, `!=`, `and`, `or` (`python:S1764`)
- **Self-assignment forbidden** (`x = x`) — `python:S1656`
- **No unreachable code after `return` / `raise` / `break` / `continue`** (`python:S1763`)

#### Security (SonarQube hotspots / Codacy bandit)

- **Never use `eval`, `exec`, `compile`, `__import__`** on untrusted input (`python:S1523`)
- **Never use `pickle`, `marshal`, `shelve`** to deserialize untrusted data (`python:S5135`)
- **Never use `subprocess` with `shell=True`** on user input (`python:S4721`)
- **Never use `assert` for security checks** — assertions are stripped with `-O` (`python:S5915`)
- **Never hard-code credentials, tokens, IPs, or URLs with secrets** (`python:S2068`, `python:S1313`)
- **No insecure hash algorithms** (MD5, SHA-1) for security purposes — use SHA-256+ (`python:S4790`)
- **No insecure TLS/SSL** — never disable certificate verification (`verify=False`) — `python:S4830`
- **No predictable random** for security tokens — use `secrets`, not `random` (`python:S2245`)
- **XML parsing must disable entity expansion** to prevent XXE — use `defusedxml` (`python:S2755`)

#### Documentation & Typing

- Public modules, classes, and functions require docstrings (Codacy `pylint:missing-docstring`)
- Type hints on every public function signature; prefer `from __future__ import annotations` for forward refs
- No `# TODO` / `# FIXME` without an associated issue link (`python:S1135`)

#### Testing Quality

- Test functions must contain at least one assertion (`python:S2699`)
- Never use `assert True` / `assert 1 == 1` as placeholders (`python:S2187`)
- Disabled tests (`@pytest.mark.skip` without reason) are flagged — always provide `reason="..."`

### Pre-Commit Verification

Before committing, run the following checks locally and ensure they pass cleanly:

```bash
# Lint with project tools (add as needed)
python -m pylint je_web_runner/
python -m flake8 je_web_runner/ --max-line-length=120 --max-complexity=10
python -m bandit -r je_web_runner/ -ll

# Type check
python -m mypy je_web_runner/

# Tests
python -m pytest test/
```

If SonarQube or Codacy is wired into CI, fix any new issues in the same PR — do not defer them with suppressions unless a justified `# noqa: <rule>` comment explains why.

## Git & Commit Conventions

- Branch model: `main` (stable) / `dev` (development)
- PRs go from `dev` to `main`
- Commit messages: concise, imperative mood (e.g., "Add element validation", "Fix driver cleanup on timeout")
- **Do NOT mention any AI tools, assistants, or language models in commit messages** — commits must read as standard developer-authored messages
- **Do NOT include `Co-Authored-By` lines referencing AI in commits**

## Testing

- Tests are located in the `test/` directory
- Test files follow the pattern `test_*.py`
- Use `pytest` as the test runner
- Integration tests require a browser driver to be available
