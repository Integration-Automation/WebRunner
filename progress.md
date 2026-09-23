# progress.md: WebRunner

Outstanding work only. When an item is done, delete it in the same commit and add a `#done` entry to `docs/updates/` (format and query commands: `docs/updates/README.md`). No finished items, no history, no rules (rules live in `CLAUDE.md`).
Item numbers (`#n`) are never reused. Tags: [DECIDE] needs the owner's decision, [BLOCKED] waits on something else, [UNVERIFIED] observed but not confirmed.
Cross-repo and workspace items live in `D:\Codes\progress.md` (relevant here: S-7, X-2, X-3, X-6, X-16).

## Open

- **#4** `je_web_runner/utils/` has about 267 flat modules without a layered index (the README groups them only by section, and `CLAUDE.md` lists them flat).
- **#6** SonarCloud on `main` (2026-09-23): 475 × `python:S5778` in `test/` (exception tests with more than one call that could raise; each `pytest.raises` / `assertRaises` block should hold only the call under test). Details in `docs/updates` U-20260923-06.
