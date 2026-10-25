# Managed read-only browser context implementation plan

> **For agentic workers:** Use superpowers:executing-plans inline. The existing execution method and
> question opt-out persist; do not introduce another planning approval round.

**Goal:** Retire input/network permanently while preserving the original managed browser context
for independently fresh, bounded read-only completion observations.
**Architecture:** A neutral host lifecycle state and an injected closed read-only view extend the
existing managed SDK. Guard/session checks retain original ownership and never open another page.
**Tech stack:** Existing Python3.10+, managed WebRunner SDK and standard-library scoped transport;
fake installed Playwright and owned loopback tests only.
**Spec:** `docs/superpowers/specs/2026-10-25-managed-readonly-context-design.md` and the original
AutoControl `docs/superpowers/plans/2026-10-23-agent-runtime.md` P5/P9 contract.
**BASE:** WebRunner84a86deace1d986f9be81451132379502662eec2; consumer9e7b6e06222486779f1a454a72ae49db15d46010.

## Global constraints

- Entirely background, no browser/desktop/device startup or native input; deferred acceptance stays deferred.
- Browser implementation stays je_web_runner/D:/Codes/WebRunner; no alternate engine or shared venv update.
- No version/dependency/credential/Tripo/generation/billing change, production checkout change or merge/deploy.
- File750/function75/parameters7/CC10/nesting4/line120; no new cycle or unjustified suppression.
- README3/Sphinx2/architecture/cross-project contracts/openProgress/updates+index ship with implementation.
- Full headless unit/safe integration evidence is distinct from excluded real-browser/native/Grid acceptance.
- Existing whole mypy/flake8/strict-Sphinx debt is compared to the exact baseline, never called clean.
- The SDK prerequisite does not complete AutoControl's provider item; retain all forty tracked gaps.

## Review focus

1. An old owner reference must not mutate after freeze, including transfers and timeout changes.
2. Failed retirement must yield no usable view and must not restore input on retry/cleanup.
3. A lost/replaced page, changed URL or UI fault must not reuse an apparently valid context ID.
4. Active transfer/callback and foreign-thread calls cannot manufacture an input-retired certificate.
5. Reads retain full bounded/secret masking rules; metadata and import success are not native evidence.

## Files and interfaces

- Create `je_web_runner/utils/agent/_managed_lifecycle.py`: host state for context identity, mode,
  frozen session/page anchor, cached view, active count and owning thread (six fields maximum).
- Create `je_web_runner/utils/agent/managed_readonly.py`: `ManagedReadOnlySession(policy,context_id,invoke)`;
  fixed typed read methods delegate a closed callback, expose no action/transfer/page/argv/script API.
- Modify `managed_browser.py`: `readonly_contract_version=1`, `context_id`,
  `freeze_readonly() -> ManagedReadOnlySession`, private live/context/read-only dispatch checks;
  preserve existing open/close/transfer/readback contracts until an explicit freeze.
- Modify `_managed_guard.py`: own neutral state; block route forwarding once mode leaves writable;
  add owning-thread guard independently of sticky UI fault checks.
- Modify `agent/__init__.py`, `api/ai.py`, root `__init__.py`: export the one SDK view type only.
- Tests: `test/unit_test/test_managed_browser_readonly.py`,
  `test_managed_browser_readonly_lifecycle.py`, `test_managed_browser_readonly_transport.py`.
- Docs: README3, local_agent_doc.rst English/Chinese, architecture.md, progress.md #22,
  owned Python example, monthly updates/index. No raw-capability WR command or global registry.

## Task 1: Same-context permanent read-only view

- [x] Add tests using `opened` from existing managed-browser tests (real SDK/guard/proxy, fake runtime).
  Assert one original page/session/context, transport closed, capabilities exact, fresh bounded
  text/value/visibility/observation reads, read timeout, unchanged launch count and no browser close.
  Parametrize original-reference `perform/upload/open_download/set_timeout` refusals before effect.
- [x] Run `python -m pytest test/unit_test/test_managed_browser_readonly.py -q` with explicit feature
  PYTHONPATH and a new owned basetemp. Expected RED: missing freeze_readonly, not browser/dependency errors.
- [x] Implement neutral state, closed view and the original-session freeze/gates from those tests.
  Successful freeze caches the same view; context/session/page anchors and origin policy stay exact.
- [x] Run the new tests plus unchanged managed_browser/readback/transfers/scoped_proxy regressions.
  Expected all pass with no real engine. Do not implement untested active/thread boundaries yet.

## Task 2: Active/thread/failure/context/transport boundaries

- [x] Write and observe RED for active-operation freeze and wrong-thread view/close before SDK access.
  Add active operation tracking and owning-thread checks; active preflight yields no certificate.
- [x] Add real retirement failure after input gate closes: no view, no resumed writes, sanitized error,
  sticky unconfirmed cleanup and no success on a second close. Add popup/dialog/crash/close and lost
  session/page/URL cases, including attempted restoration after context loss.
- [x] Add bounded/secret readback on the new view, capabilities invalidation after close, separate
  owner isolation, readonly context manager cleanup and immutable capability-dict copy behavior.
- [x] Add controlled loopback proof that held owned sockets/listener retire before the view is returned,
  readonly routes abort even approved URLs, and no new upstream connection can start.
- [x] Each case must fail for the stated missing behavior before its implementation; run the complete
  current managed/transport family after the final source change. Never weaken existing expectations.

## Task 3: Public SDK/documentation and truthful consumer boundary

- [x] Verify exact public export identity through agent, api.ai and root, integer readonly contract1,
  inert import/construction and no raw session identifier accepted from JSON.
- [x] Align README3, Sphinx2, architecture cross-project contract and an explicit host-only Python
  example. Distinguish implemented SDK from not-yet-implemented AutoControl retained-helper provider.
- [x] Keep progress.md #22 open with the remaining consumer/provider/context-transfer/deployment/native
  work, plus existing #20/#21 deferrals and #23 debt. Do not delete the consumer's forty-item gap.

## Task 4: Verification, artifacts and atomic stage delivery

- [x] Run whole Pylint/flake8/Bandit/mypy and scoped comparisons against84a; inspect all added findings
  and actual import cycles, not only numeric scores. Check budgets and unchanged WR command/schema.
- [x] Run all unit tests and all safe integrations; explicitly exclude known real-browser/native/Grid
  modules and optional real-model/scheduler/soak paths because acceptance is deferred. Record exact
  command/counts/exclusions. Do not invoke the nominal full suite that starts installed real browsers.
- [x] Build strict docs and compare existing warnings to baseline; run dependency/build diagnostics,
  wheel/sdist byte checks and isolated no-deps installation/public SDK proof without browser startup.
- [x] Add actual verification/update entry+index atomically; stage only owned WebRunner files,
  commit/push feat/managed-browser-sessions and verify remote/clean status. No production branch push.
- [x] Record the completed prerequisite and remaining AutoControl provider/remote steps before the next
  task. The original goal stays active; one whole-branch review remains for the actual whole-plan end.

Self-review: all five Review Focus items have owning tests; source/broker integration and real-device
contracts remain explicitly scheduled follow-ups rather than fake capability declarations. No new
browser, context restoration, input replay or broader task-read permission is an acceptable shortcut.
