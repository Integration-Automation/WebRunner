# docs/updates: update log index

`progress.md` holds only work that is **not done yet**. Everything that *was* done (what changed, measured numbers, decisions, snapshots) is recorded here: **one batch file per month**, one entry per piece of work, each entry with a fixed-format ID and tags, and one row per entry in the index below.

> No TODOs here. If an entry mentions something still open, it only points to it (e.g. "open item: `progress.md` #3"); the item itself lives in `progress.md`.

## How to query

Run from the repository root:

| To find | Command |
|---|---|
| every entry, one line each | `rg -n "^## U-2" docs/updates` |
| entries of one type | `rg -n "^## U-2.*#done" docs/updates` |
| entries with a topic tag | `rg -n "^## U-2.*#<tag>" docs/updates` |
| one day or one month | `rg -n "^## U-202609" docs/updates` |
| the full text of one entry | `rg -n -A 60 "^## U-20260922-01" docs/updates` |
| any keyword | `rg -n "keyword" docs/updates` |

Without `rg`: `git grep -n "^## U-2" -- docs/updates`, or in PowerShell `Select-String -Path docs/updates/*.md -Pattern '^## U-2'`.

## Entry format

```markdown
## U-YYYYMMDD-NN · YYYY-MM-DD · one-line title · #type #topic

- **What**: ...
- **Result / numbers**: ...
- **Files**: `path` ...
- **Evidence**: commit, file:line, link ...
- **Open items**: none / see `progress.md` ...
```

- **ID**: `U-` + date + two-digit sequence for that day. IDs are never renumbered or reused, so code comments and other documents can cite them.
- **Type tag** (exactly one): `#done` finished `progress.md` item, `#snapshot` measurement or inventory, `#decision`, `#incident`, `#migration`, `#docs`, `#release`.
- Topic tags are free-form (`#mcp`, `#wayland`, ...).
- Keep conclusions, numbers, files and evidence; drop the reasoning trail and dead ends.

## Batch rules

1. One file per month: `docs/updates/YYYY-MM.md`. Append new entries at the end.
2. Over about 800 lines, continue in `YYYY-MM-b.md` (then `-c`) and list it in the batch table below.
3. **Claim the ID under a lock.** Several sessions may write this log at the same time (for example parallel autonomous runs), and without a lock two of them pick the same number:
   1. `mkdir docs/updates/.id-lock`. Creating a directory is atomic, so only one writer succeeds. If it already exists, someone else is claiming: wait a few seconds and retry. A lock older than 10 minutes is stale and may be removed.
   2. Find the day's last number with `rg -n "^## U-YYYYMMDD" docs/updates` and write the heading line and the index row.
   3. `rmdir docs/updates/.id-lock`, then fill in the body. Git never tracks the empty lock directory.
   4. Before committing, `rg -c "^## U-<your ID>" docs/updates` must report one match in total. If not, renumber your entry under the lock and fix its index row. Whoever merges a branch renumbers entries that reuse an ID.
4. **One line per index row**: title only (about 60 characters), no summary.
5. Never rewrite a recorded entry. Correct it with a new `#decision` or `#incident` entry and add "→ corrected in U-..." to the old one.

## When a `progress.md` item is done

In the same commit: delete the item from `progress.md`, add a `#done` entry here that names it, and add its index row.

---

## Index (newest first)

| ID | Date | Title | Tags | Batch |
|---|---|---|---|---|
| U-20260925-02 | 2026-09-25 | Translated READMEs link back to the repository root | #docs #tests | [2026-09](2026-09.md) |
| U-20260925-01 | 2026-09-25 | Dependabot waits 7 days before proposing a new release | #ci #security #deps | [2026-09](2026-09.md) |
| U-20260924-01 | 2026-09-24 | Pin workflow actions by commit; keep checkout credentials only where a job pushes | #ci #security | [2026-09](2026-09.md) |
| U-20260923-20 | 2026-09-23 | One possibly-raising call per exception-test block (S5778) | #done #tests #sonar | [2026-09](2026-09.md) |
| U-20260923-19 | 2026-09-23 | Generated, layered index of the utils subpackages | #done #docs | [2026-09](2026-09.md) |
| U-20260923-18 | 2026-09-23 | Test workflows install a hash-locked ci.txt and test the checkout | #ci #security | [2026-09](2026-09.md) |
| U-20260923-17 | 2026-09-23 | Release 0.0.90 after Codacy's two test findings | #done #release #ci | [2026-09](2026-09.md) |
| U-20260923-06 | 2026-09-23 | Six text scanners made linear; SonarCloud status re-checked | #done #performance #security | [2026-09](2026-09.md) |
| U-20260923-12 | 2026-09-23 | README: one themed More Capabilities section | #docs | [2026-09](2026-09.md) |
| U-20260923-11 | 2026-09-23 | Release job installs locked tooling | #ci #security | [2026-09](2026-09.md) |
| U-20260923-10 | 2026-09-23 | Counts quoted in the docs are checked against the code | #done #docs #tests | [2026-09](2026-09.md) |
| U-20260923-09 | 2026-09-23 | Three email patterns made linear | #done #performance #security | [2026-09](2026-09.md) |
| U-20260923-08 | 2026-09-23 | The socket server no longer reads sys.argv | #change #socket #security | [2026-09](2026-09.md) |
| U-20260923-07 | 2026-09-23 | Ten small SonarCloud findings cleared | #done #quality | [2026-09](2026-09.md) |
| U-20260923-05 | 2026-09-23 | Dependabot targets dev; setup-python v7 | #done #ci #deps | [2026-09](2026-09.md) |
| U-20260923-04 | 2026-09-23 | Executor builtins become an allowlist | #done #security #executor | [2026-09](2026-09.md) |
| U-20260923-03 | 2026-09-23 | dev.toml back in step with pyproject.toml | #done #packaging | [2026-09](2026-09.md) |
| U-20260923-02 | 2026-09-23 | Write down the public API and the deprecation policy | #done #docs #api | [2026-09](2026-09.md) |
| U-20260923-01 | 2026-09-23 | Release 0.0.89 with the UTF-8 log encoding | #done #release | [2026-09](2026-09.md) |
| U-20260922-06 | 2026-09-22 | Regression test for the UTF-8 log encoding | #done #logging #tests | [2026-09](2026-09.md) |
| U-20260922-05 | 2026-09-22 | Open WEBRunner.log as UTF-8 | #done #logging #encoding | [2026-09](2026-09.md) |
| U-20260922-04 | 2026-09-22 | Contract test for the legacy CLI flags | #done #tests | [2026-09](2026-09.md) |
| U-20260922-03 | 2026-09-22 | Point project URLs at the current repository | #done #metadata | [2026-09](2026-09.md) |
| U-20260922-02 | 2026-09-22 | Stop tracking .idea/ | #done #housekeeping | [2026-09](2026-09.md) |
| U-20260922-01 | 2026-09-22 | Adopt progress/architecture/docs-updates rules | #docs #migration | [2026-09](2026-09.md) |

## Batches

| File | Period | Entries |
|---|---|---:|
| [2026-09.md](2026-09.md) | 2026-09 | 25 |
