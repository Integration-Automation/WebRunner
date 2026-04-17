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
