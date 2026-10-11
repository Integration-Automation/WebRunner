# progress.md: WebRunner

Outstanding work only. When an item is done, delete it in the same commit and add a `#done` entry to `docs/updates/` (format and query commands: `docs/updates/README.md`). No finished items, no history, no rules (rules live in `CLAUDE.md`).
Item numbers (`#n`) are never reused. Tags: [DECIDE] needs the owner's decision, [BLOCKED] waits on something else, [UNVERIFIED] observed but not confirmed.
Cross-repo and workspace items live in `D:\Codes\progress.md` (relevant here: X-6, X-12, X-13, X-27).

## Open

- **#20** Two-way bridge with AutoControl (`je_auto_control`, AutoControlGUI repo; workspace X-27), what is left: [BLOCKED: needs a desktop nobody is using, with no Jeffrey_RPA batch and no other window able to come in front of Chrome] run `test/integration_test/test_autocontrol_native_desktop.py` with `WEBRUNNER_NATIVE_DESKTOP_TESTS=1` and `je_auto_control` 0.0.225 or newer (the first release with `AC_write_secret`; the local AutoControlGUI working tree is still on an older commit and has to be pulled, or the release installed, first). `WR_ac_click_element_native`, `WR_ac_fill_native_file_dialog` and `WR_ac_assert_image_on_screen` have not yet passed on a real desktop, and `WR_ac_basic_auth` has passed there once. The test also checks the page-to-screen mapping against where AutoControl finds the same element's image.
