# progress.md: WebRunner

Outstanding work only. When an item is done, delete it in the same commit and add a `#done` entry to `docs/updates/` (format and query commands: `docs/updates/README.md`). No finished items, no history, no rules (rules live in `CLAUDE.md`).
Item numbers (`#n`) are never reused. Tags: [DECIDE] needs the owner's decision, [BLOCKED] waits on something else, [UNVERIFIED] observed but not confirmed.
Cross-repo and workspace items live in `D:\Codes\progress.md` (relevant here: S-7, X-2, X-3, X-6, X-16).

## Open

- **#7** [DECIDE] 189 of the 265 `je_web_runner/utils` subpackages are re-exported by no `je_web_runner.api` facade theme, so `docs/reference/utils_index.md` lists them under "Other feature subpackages". Add facade themes for them (the index picks new themes up on regeneration), or keep the facade to the current eleven.
