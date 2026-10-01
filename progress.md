# progress.md: WebRunner

Outstanding work only. When an item is done, delete it in the same commit and add a `#done` entry to `docs/updates/` (format and query commands: `docs/updates/README.md`). No finished items, no history, no rules (rules live in `CLAUDE.md`).
Item numbers (`#n`) are never reused. Tags: [DECIDE] needs the owner's decision, [BLOCKED] waits on something else, [UNVERIFIED] observed but not confirmed.
Cross-repo and workspace items live in `D:\Codes\progress.md` (relevant here: X-6, X-12, X-13, X-27).

## Open

- **#20** Two-way bridge with AutoControl (`je_auto_control`, AutoControlGUI repo; workspace X-27), what is left:
  1. [BLOCKED: AutoControlGUI's keyboard module is frozen while Jeffrey_RPA batches run] `WR_ac_basic_auth` (env-var names, never values) in `je_web_runner/utils/autocontrol_bridge/native.py`. AutoControl's `write` / `type_keyboard` (`je_auto_control/wrapper/auto_control_keyboard.py`) log the typed text, record it and return it, so a password typed through them reaches AutoControl's log and both run records. It needs a typing call there that does none of that. Answering in-protocol is no substitute: Selenium's BiDi `add_auth_handler` passes on Firefox, but chromedriver never acts on `continueWithAuth` while a classic `get` waits (a top-level page behind basic auth times out). Playwright already takes `http_credentials` through `WR_pw_set_context_options`. Add it to the MCP server's `UNSAFE_COMMANDS` and both repos' `architecture.md` §6.
  2. Run `test/integration_test/test_autocontrol_native_desktop.py` with `WEBRUNNER_NATIVE_DESKTOP_TESTS=1` and `je_auto_control` installed, on a desktop nothing else is driving. `WR_ac_click_element_native`, `WR_ac_fill_native_file_dialog` and `WR_ac_assert_image_on_screen` have only run against a faked AutoControl, because Jeffrey_RPA's batch shares this machine's desktop. The test also checks the page-to-screen mapping against where AutoControl finds the same element's image.
