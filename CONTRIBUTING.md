# Contributing to WebRunner

Thanks for your interest in improving WebRunner (`je_web_runner`). This
guide covers the local setup, the checks we expect to pass, and the branch
/ PR conventions.

## Development setup

WebRunner targets **Python 3.10+**.

```bash
# Runtime dependencies
pip install -r requirements.txt

# Development dependencies (tests, linters, docs, build tooling)
pip install -r dev_requirements.txt
```

## Running the tests

```bash
# Whole suite (unit + integration; e2e tests skip without a Selenium hub)
python -m pytest test/

# Unit tests only
python -m pytest test/unit_test/test_*.py
```

The pure-Python unit suite needs no browser. Integration tests spawn
short-lived subprocesses. The real-browser e2e tests under
`test/e2e_test/` skip cleanly unless `WEBRUNNER_E2E_HUB` points at a
reachable Selenium Grid (see `docker/`).

## Before opening a pull request

Run the linters and keep them clean (no new findings):

```bash
python -m flake8 je_web_runner/ --max-line-length=120 --max-complexity=10
python -m pylint je_web_runner/
python -m bandit -r je_web_runner/ -ll
python -m mypy je_web_runner/
```

Please also:

- Add or update tests for any behaviour you change.
- Keep public functions type-hinted and documented.
- Avoid introducing new static-analysis issues (SonarQube / Codacy).

## Branches and commits

- `main` is the stable branch; `dev` is the development branch.
- Open pull requests **from `dev` into `main`**.
- Write concise, imperative commit messages (e.g. "Add element
  validation", "Fix driver cleanup on timeout").

## Reporting security issues

Do **not** file security vulnerabilities as public issues — see
[SECURITY.md](SECURITY.md) for the private disclosure process.
