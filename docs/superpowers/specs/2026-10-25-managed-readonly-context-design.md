# Managed browser context retirement for read-only completion

The remaining AutoControl P5/P9 contract requires independently fresh completion reads from the
original application context after input authority has retired. Today normal cleanup closes that
context and a fresh helper opens a different blank browser. Neither historical observations nor a
new page can establish the original application's current state.

## Scope and delivery boundary

1. This independently usable SDK stage adds a permanent read-only transition to an existing
   `ManagedBrowserSession`; it preserves the original page/context and immutable origin policy.
2. The following AutoControl stage binds actual helper input retirement and retained context ownership
   to existing completion review/create/finish/skill operations and their shared surfaces. It must not
   advertise browser read-only completion before that provider is implemented and verified.
3. Remote device readers need the real provider/generation/settlement sources already tracked under
   P7. This SDK transition does not establish those sources or cross-host evidence authority.

The original P0-P9 goal, forty tracked AutoControl items, native/device/browser and twenty-four-hour
acceptance deferrals remain. No new dependency, version change, production deployment, credential
operation, paid service, desktop input, visible browser or real browser acceptance is part of this stage.

## Approaches and ruling

- Opening a fresh browser is insufficient: the original authenticated/app state is lost.
- General CDP attachment or a caller-supplied page is insufficient: it has neither this managed
  context's ownership nor a permanent no-input contract.
- Chosen: monotonically freeze the original SDK session, retire its private network transport,
  and return a closed read-only view. Its original owner reference also loses mutation authority.
  This requires retained-context ownership in the later AutoControl helper stage; it does not
  weaken the current consumer refusal while that integration is missing.

These are implementation rulings under the user's existing inline execution and question opt-out.

## SDK contract

`ManagedBrowserSession.readonly_contract_version = 1` declares API support, not runtime readiness.
`freeze_readonly() -> ManagedReadOnlySession` uses only an already-open, original allowed-origin
page. It never launches, attaches, navigates, restores cookies, or substitutes another context.

An owning-thread preflight rejects closed/faulted/missing contexts and active operations. Once the
transition starts, its mode permanently leaves writable before transport retirement. Every later
typed action, upload, download and original-owner timeout mutation is refused before effect.
Network retirement failure produces no reader, retires the owner and preserves unconfirmed cleanup;
it cannot be retried into input authority. Cleanup remains explicit and affects only owned resources.

The new view exposes `policy`, `context_id`, `capabilities()`, `url`, `observe(step=0)`,
`text(selector='body', frame='')`, `read_value(selector, frame='')`, `visible(selector, frame='')`,
`link(selector, frame='')`, `set_timeout(timeout)`, `close()` and context management. Reads use the
existing bounded, masked fixed scripts; timeout changes only bound reads and never create input.
The view carries an injected closed host callback, not model data, an argv, script or page handle.

Capabilities are exactly `{contract:1,input_supported:false,network_retired:true,context_id:<id>}`
only while the same original context is live and its network retirement is confirmed. Context ID is
an opaque identity, not an authorization grant. Each call checks original session/page identity,
owner thread, immutable origin policy, sticky UI faults, the URL anchored at freeze and pre/post URL continuity. Lost/replaced
contexts remain unusable; a cached capability dictionary never authorizes a later operation.

Repeated successful freeze returns the same view/identity. Closing either handle closes only this
owner and invalidates the view; repeated close stays idempotent. Popup/dialog/download/filechooser,
page crash/close and SDK failures retain current sticky guards and sanitized errors. Foreign-thread
access is refused before SDK use. An active transfer/operation cannot certify input retirement.

## Structure and verification

Keep mutable lifecycle data in neutral `_managed_lifecycle.py` (at most six dataclass fields), the
closed typed view in `managed_readonly.py`, and actual SDK/context checks in `managed_browser.py`.
`ContextGuard` owns lifecycle state and rejects all routes after freezing begins. No new import cycle,
global wrapper, raw JSON handle, WR command, GUI session registry or browser engine is introduced.
Public SDK class exports use the existing agent/API/root facades; consumer GUI remains its existing
completion workflow once the following helper/provider integration is complete.

Tests use the real SDK/owner/guard/proxy with a fake installed Playwright factory and controlled
loopback sockets. They prove same context, fresh bounded reads, old-reference refusals, retirement
failure, active-call/thread fencing, sticky context loss and isolated cleanup. Native browser tests
are not run. Existing masked readback/transfer/lifecycle tests remain unchanged and must pass.
