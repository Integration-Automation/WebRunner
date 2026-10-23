# progress.md: WebRunner

Outstanding work only. When an item is done, delete it in the same commit and add a `#done` entry to `docs/updates/` (format and query commands: `docs/updates/README.md`). No finished items, no history, no rules (rules live in `CLAUDE.md`).
Item numbers (`#n`) are never reused. Tags: [DECIDE] needs the owner's decision, [BLOCKED] waits on something else, [UNVERIFIED] observed but not confirmed.
Cross-repo and workspace items live in `D:\Codes\progress.md` (relevant here: X-6, X-12, X-13, X-27).

## Open

- **#20** Two-way bridge with AutoControl (`je_auto_control`, AutoControlGUI repo; workspace X-27), what is left: [BLOCKED: needs a desktop nobody is using, with no Jeffrey_RPA batch and no other window able to come in front of Chrome] run `test/integration_test/test_autocontrol_native_desktop.py` with `WEBRUNNER_NATIVE_DESKTOP_TESTS=1` and `je_auto_control` 0.0.225 or newer (the first release with `AC_write_secret`; the local AutoControlGUI working tree is still on an older commit and has to be pulled, or the release installed, first). `WR_ac_click_element_native`, `WR_ac_fill_native_file_dialog` and `WR_ac_assert_image_on_screen` have not yet passed on a real desktop, and `WR_ac_basic_auth` has passed there once. The test also checks the page-to-screen mapping against where AutoControl finds the same element's image.

- **#21** [UNVERIFIED] Deferred at the owner's request: do not start or resume the 24-hour acceptance without a new explicit instruction. Remaining acceptance is the full 24-hour run in `scripts/verify_issue_worker.py`, including its final container/browser gates, against unchanged sources. Interrupted evidence is retained at `D:/WebRunnerValidation/runtime-20261023/attempt-04`; any resumed run needs a fresh attempt directory. Short or interrupted runs do not substitute for full-duration acceptance.

- **#22** [WIP] Managed browser integration for AutoControlGUI: connect the owned origin transport to an isolated browser session before navigation, then expose the reviewed managed target/observation/action seam in AutoControlGUI. Download/read-back and failure retirement integration remain open. Browser/native acceptance remains unverified and the existing owner-requested acceptance pauses remain in force. Source worktrees: WebRunner `.worktrees/agent-managed` and AutoControlGUI `.worktrees/agent-runtime`.

- **#23** [TODO] Resolve existing whole-package quality debt: mypy reports 510 errors in 75 files, including missing requests stubs; flake8 reports 116 findings at the project limits. Strict Sphinx also reports viewport docstring markup, duplicate MCP declarations/section labels and ambiguous builtin references. Baseline comparison against unchanged `c400466c` is recorded in `docs/updates/2026-10-b.md`.
