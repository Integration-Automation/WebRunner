# progress.md: WebRunner

Outstanding work only. When an item is done, delete it in the same commit and add a `#done` entry to `docs/updates/` (format and query commands: `docs/updates/README.md`). No finished items, no history, no rules (rules live in `CLAUDE.md`).
Item numbers (`#n`) are never reused. Tags: [DECIDE] needs the owner's decision, [BLOCKED] waits on something else, [UNVERIFIED] observed but not confirmed.
Cross-repo and workspace items live in `D:\Codes\progress.md` (relevant here: S-7, X-2, X-3, X-6, X-16).

## Open

- **#1** Release the UTF-8 log encoding (`je_web_runner/utils/logging/loggin_instance.py`, U-20260922-05; guarded by `test/unit_test/test_logging_encoding.py`): merge `dev` into `main` so CI publishes it. Jeffrey_RPA loads this working tree through `sys.path` and waits for the release (workspace X-2).
- **#2** `dev.toml` (≈:17-23) lacks `Pillow>=12.3.0` although ≈:16 says it mirrors `pyproject.toml`.
- **#3** [UNVERIFIED] The SonarCloud snapshot of 2026-04-26 (`issues.json`, `hotspots.json`, gitignored) listed 9 issues (6 × S3776) and 2 hotspots in TO_REVIEW; re-check against the current analysis.
- **#4** `je_web_runner/utils/` has about 267 flat modules without a layered index, and README has five sections titled "Even More Capabilities".
- **#5** [DECIDE] Write down the public API and a deprecation policy. Downstream code imports internal paths `je_web_runner.utils.executor.action_executor.executor` (AutoControlGUI) and `je_web_runner.utils.logging.loggin_instance` (Jeffrey_RPA) — keep them or give them a public home (workspace X-3).
