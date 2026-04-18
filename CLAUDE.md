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
    └── xml/                 # XML utilities
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
