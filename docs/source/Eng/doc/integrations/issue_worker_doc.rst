Local issue worker
==================

The issue inbox accepts only open, unassigned GitHub/Jira Cloud issues labeled
``automation-ready``. GitHub pull requests are excluded. The repository is fixed
to ``Integration-Automation/WebRunner``, with ``dev`` as the review target.
Jira requires an explicit project allowlist and account ID, not a workflow status name.

Copy ``examples/issue-worker.example.json`` and configure the installed local model,
bot identities and Jira site. Remove the Jira URL/projects/bot fields to use GitHub
alone. Credentials are environment variable references, never token values in JSON.
Relative state paths resolve against the config file. SQLite WAL stores jobs and
checkpoints. One renewable lease serializes processing on a single host.

.. code-block:: python

    from je_web_runner.api.orchestration import IssueInbox, IssueWorkerConfig

    inbox = IssueInbox(IssueWorkerConfig.load("issue-worker.json"))
    try:
        print(inbox.discover(dry_run=True))  # platform reads only; no queued jobs
        inbox.discover()  # queues eligible issues without claiming them remotely
    finally:
        inbox.close()

Polling never overwrites an in-flight requirement snapshot. Human descriptions and
comments determine its revision; bot progress does not. Failed/cancelled/needs-info
jobs need an explicit retry and a restored ready label. Platform HTTP rejects
redirects, does not blindly retry writes, and reports rate limits without response
bodies or credential values. Existing Jira issue-creation APIs remain unchanged.

Isolated local coding
---------------------

``CodeProcessor`` uses the shared local-only Ollama transport. It supports bounded
file reads, literal search, checked unified patches and host-owned named checks.
The model cannot execute host shell commands or publish changes. A separate clone
and detached worktree hold each run, leaving the live checkout unchanged.

Install Podman and an open-source local model separately. Prepare the image once:

.. code-block:: bash

    podman build -f docker/IssueWorker.Containerfile -t localhost/webrunner-issue-worker:local .

The build context excludes source secrets and git data. Runtime containers never
pull, have no external network, run as a non-root user with dropped capabilities,
and receive a read-only source export without .git or credential files. Only the
host-configured check argv runs. Time and output limits stop runaway checks.

Text patches are fenced to source/tests/docs/examples; workflows, dependency locks,
versions, credentials, release settings and repository policy are protected.
Existing test assertions/functions are preserved and added skip/xfail escapes are
flagged. Binary changes and rename syntax require manual handling (text delete/add
is supported). Limits are 20 files, 1000 changed lines, 100 tool operations, two
validation rounds and 60 minutes by default. Baseline and final check results are
recorded against exact git tree IDs; model-declared completion cannot bypass checks.

Run and review
--------------

The worker supports bugs, new features, refactors, tests and documentation. Configure
a local model with ``OLLAMA_NO_CLOUD=1`` and restart Ollama. Both its cloud-disabled
status and installed local weights are checked. GitHub credentials need repository
Contents, Issues and Pull requests write permissions, with ``github_bot`` matching
the authenticated login. Jira needs browse/assign/edit/comment permissions and a
matching accountId. No workflow-transition permission is required.

.. code-block:: bash

    python -m je_web_runner.issue_worker run --config issue-worker.json --dry-run
    python -m je_web_runner.issue_worker run --config issue-worker.json
    python -m je_web_runner.issue_worker watch --config issue-worker.json
    python -m je_web_runner.issue_worker status --config issue-worker.json
    python -m je_web_runner.issue_worker retry --config issue-worker.json --issue jira:WR-123

``run`` handles at most one job; ``watch`` polls every 60 seconds by default. Idle,
preview and reviewed-PR delivery return exit status 0; failure, incomplete work or
dependency deferral or pending platform delivery return 1. Watch's first Ctrl-C drains;
a second interrupts with exit 130. Retry is explicit: restore
``automation-ready`` first; another person's assignment is never taken over.
Jira and GitHub sources both deliver PRs to the configured GitHub WebRunner repo.

Python ``IssueWorker(config)`` exposes ``run_once``, ``watch``, ``status`` and
``retry``; call ``close`` in ``finally``. ``IssueInbox`` previews or queues work
without starting coding. MCP ``webrunner_issue_enqueue`` and
``webrunner_issue_status`` use only the host's ``WEBRUNNER_ISSUE_CONFIG``; they do
not accept config paths, command argv or permission changes from a caller.

Processing uses queued/claimed/analyzing/fixing/validating/publishing/awaiting_review
states, with needs_info/failed/cancelled stops. Reports live in the configured state
directory under ``reports``; SQLite remains the authoritative state. Checkpoints
resume work after crashes, including validation pinned to exact tree IDs and pending
progress messages. The same state directory cannot silently change platform origins.

Before each change checkpoint and publication, the worker re-reads readiness,
ownership and human requirements. Changes cancel the run. Publication also rejects
an advanced dev baseline, unvalidated tree, changed remote branch or changed PR head.
A successful PR POST with a lost response is discovered by branch/run marker before
any retry, so a second PR is not created. One bot progress comment is updated; final
labels remove automation-ready and mark review/needs-info/failure/cancellation.
Only the expected bot-owned assignment's labels are changed.

The host publisher uses GitHub Git Database APIs to create the exact validated tree,
a deterministic commit and its private automation branch, then opens a PR to dev.
No access token is written into git configuration, model prompts, containers or
reports. It never merges or closes the source issue. Human review remains responsible
for whether the implemented behavior satisfies the requirement; passing checks alone
are not a proof of business correctness. Prebuilt image dependencies may be downloaded
during preparation, but execution has no paid provider fallback.

Verification
------------

The local integration fixture supplies GitHub, Jira and Ollama HTTP endpoints and
real temporary git repositories. It reproduces a failing test, applies the patch,
runs real pytest, creates one simulated PR and recovers a lost creation response.
No live issue, PR or Jira site is modified by these tests. Real Podman verification
is optional: install the engine/image and set ``WEBRUNNER_ISSUE_IMAGE`` before
running ``test/unit_test/test_issue_coding.py``. This option runs a real offline
container; the normal HTTP fixture does not claim to test container isolation.

MCP issue settings are parsed and frozen when the server builds its tools. Restart
the server after changing the host config; another tool loading environment files
cannot redirect these issue tools. Pagination guards reject repeated result pages
and multi-page token cycles instead of polling indefinitely.

Before activation, prepare these GitHub repository labels: ``automation-ready``,
``automation-running``, ``automation-review``, ``automation-needs-info``,
``automation-failed`` and ``automation-cancelled``. Jira uses the same label names.

Readiness and operational health
----------------------------------------

Use diagnostics, preview, a manual job, then watch, in that order:

.. code-block:: bash

    python -m je_web_runner.issue_worker doctor --config issue-worker.json
    python -m je_web_runner.issue_worker doctor --config issue-worker.json --platform --json
    python -m je_web_runner.issue_worker health --config issue-worker.json --json
    python -m je_web_runner.issue_worker stop --config issue-worker.json

Doctor checks Git, writable local state/SQLite, Podman and its installed image, and
Ollama's cloud-disabled status and installed model. It never generates, installs,
pulls or starts services. A temporary SQLite probe is created and removed locally;
no issue queue is created. Only ``--platform`` enables platform reads: actor identity,
GitHub repository/dev/required labels, and allowed Jira projects. Jira labels are
free-form and need no label catalogue. Requests are GET-only; effective write
permissions remain explicitly unverified. Exit 0 means all required checks passed;
exit 1 means at least one failed. JSON contains ready/checks and each check's
name/status/required/code/hint, without raw HTTP or subprocess output.

Health reads local state (initializing local tables if needed), without contacting
platforms or models. Healthy exits 0, degraded exits 1, stopped/stale exit 2. JSON
includes instance, PID, start time, heartbeat, phase/current issue, last completed
poll, error and drain request. Heartbeats run independently every ten seconds;
45 seconds without one is stale. Stop exits 0 and targets only the live instance;
without one it returns stop_requested=false and leaves no future stop flag.
An active job finishes within its original deadline. Idle waits check drain every
250 ms; in-progress diagnostics and HTTP calls retain their bounded timeouts.
The first watch Ctrl-C drains; a second interrupts with exit 130. Normal drain exits 0.

Watch checks local dependencies before intake and pauses/rechecks on outages.
Infrastructure failures during coding preserve resumable jobs; their existing total
deadline is not extended by downtime. A separate daemon lease prevents two watches
or a concurrent manual run in one state directory. The additive worker_runtime
table leaves existing job states intact. Operational logs are at logs/worker.log
under state, with a 5 MB limit and five backups. They omit issue/model context;
worktrees and historical reports are not deleted automatically.
Containers carry a state-directory digest label. Under the job lease, recovery
removes only matching containers with the worker's generated name pattern;
other states/manual containers are untouched. Doctor never performs this cleanup.

Python exposes ``IssueDoctor(config).check(include_platform=False)`` and
``IssueWorker.health()`` / ``request_stop()``. MCP retains queue/status tools only.

Windows login task
------------------

Prepare services and credentials in the same user's environment first. Tasks store
absolute Python/script/config paths, never tokens:

.. code-block:: powershell

    .\scripts\issue_worker_task.ps1 -Action Install -Config .\issue-worker.json
    .\scripts\issue_worker_task.ps1 -Action Start -Config .\issue-worker.json
    .\scripts\issue_worker_task.ps1 -Action Status -Config .\issue-worker.json
    python -m je_web_runner.issue_worker stop --config issue-worker.json
    # Wait for the task to stop before removing it.
    .\scripts\issue_worker_task.ps1 -Action Remove -Config .\issue-worker.json

The default Python is this checkout's .venv\Scripts\python.exe; override with
``-Python``. Keep the script and checkout available. Task names use a config-path
digest; only owned tasks can be changed. Tasks use current-user interactive login,
limited privileges, a hidden window, IgnoreNew, three one-minute failure restarts,
and no execution time limit. Install does not start the task. Remain logged in;
this is not a logoff-persistent service. Neither Ollama nor Podman is started
automatically. Drain running tasks before updating or removing them.

Required real local acceptance
------------------------------

Normal tests may skip unavailable real services. This dedicated entry point fails
when prerequisites are missing and never counts skipped execution as acceptance:

.. code-block:: powershell

    $env:WEBRUNNER_ISSUE_MODEL = 'YOUR_INSTALLED_LOCAL_MODEL'
    $env:WEBRUNNER_ISSUE_IMAGE = 'localhost/webrunner-issue-worker:local'
    python scripts/verify_issue_worker.py --soak-hours 0
    python scripts/verify_issue_worker.py  # end-to-end plus a default 24-hour soak

Only the model and containers are real; both platforms use local HTTP fixtures.
Checks cover both sources, failing-before/passing-after evidence, uncertain PR
creation recovery, same-PR review corrections with lost-reference recovery,
non-root/offline containers, read-only source/root and absent platform credentials.
The soak records observed 429/503/TCP failures, successful polling recovery and
distinct watch instances in ``soak-evidence.json`` under its test state directory.
Runs of at least 150 seconds require every fault and a restart to be observed;
full acceptance still requires 24 hours. Separate process tests cover crashes,
lease takeover and CLI stop.
Set ``WEBRUNNER_TEST_SCHEDULER=1`` to register and remove a unique temporary Windows
task; that test never starts the task or changes production tasks.
Report missing model/Podman and an uncompleted 24-hour soak as unverified separately.

PR review revisions
-------------------

Set ``review_enabled=true`` to let run/watch poll delivered PRs when no active job
needs resuming, before discovering new issues. Legacy configs default to disabled;
the example explicitly enables it. ``review_poll_seconds`` defaults to 60 and
``max_review_rounds`` to three. Only the same bot/run marker/repository/automation
branch may be revised.

Actionable feedback includes current-head CHANGES_REQUESTED/COMMENTED reviews and
their inline comments, plus PR discussion comments starting with ``/webrunner fix``.
Human authors must be User accounts with API-confirmed write/maintain/admin access.
Bots and read-only collaborators cannot trigger revisions. Later approval/dismissal
supersedes an author's prior review. Current-head failed check runs and latest commit
statuses also qualify. The worker never downloads external logs, reruns remote CI
or adds paid services. Tokens need read access to reviews/checks/statuses and
collaborator permissions in addition to the original delivery permissions.

Feedback is capped at 4,000 characters per event and 50 events/20,000 characters
per batch. Oversized feedback stops intake for that PR and requests summarization;
requirements are never silently truncated and acknowledged. Feedback is redacted and atomically claimed
in SQLite before local inference. Feedback is data, never host command authority.
Each round uses a separate worktree rooted at the saved PR head, runs all checks
again, and retains cumulative file/line limits against the original dev baseline.
Publication fast-forwards the same branch with force=false, adds one validation
comment for that round, and preserves the human-editable PR body. It never opens
another PR, merges or closes the source issue. Uncertain ref/comment replies are
reconciled before retry, without rerunning the model or duplicating delivery.

Checkpoints re-read source requirements/ownership and PR head/open state. The source
must remain bot-owned with automation-review/automation-running; removing these
labels cancels work. External head changes, an advanced dev baseline, closed PRs or
round exhaustion stop automatic revisions, exposed as review_blocked/review_closed
in status. Coding failures or needs_info retain the PR for manual handling; the
existing retry guard prevents a duplicate PR.

After clarification or environment repair, restore automation-review on the source
and invoke ``retry-review --config issue-worker.json --issue github:123`` (Jira keys
also work), or Python ``IssueWorker.retry_review(key)``. This explicit operation
accepts refreshed source requirements, retains the same run/PR and requeues unfinished
feedback. It still rejects external heads, closed PRs, pending reports and host round
exhaustion. It performs no platform writes. Exhausted rounds require an explicit
host configuration increase; the model cannot remove the limit.

Requirement analysis and browser acceptance
------------------------------------------------------------

Set ``requirements_enabled=true`` to use the same local model for a summary, task
kind, C1/C2 acceptance criteria and concrete clarification questions before coding.
Legacy configs default to disabled; examples explicitly enable it. Analysis consumes
one tool operation, allows one malformed-response correction, and questions stop
with needs_info before baseline execution or patching. Criteria may reference only
host-owned check/browser names, or explicitly require manual review. Models cannot
supply commands, URLs, privileges or their own pass flags.

Plans support 20 criteria of up to 1,000 characters, plus 20 questions of 500
characters. Analysis versions bind source requirements and revision feedback; final
evidence binds the published git tree. ``AcceptanceCriterion``/``RequirementPlan``
are exported by api.orchestration. PR evidence reports criterion/name/tree/outcome.
evidence_passed means supporting host checks passed, not complete business proof;
business_verified remains false and human review is required.

See ``examples/issue-worker-browser.example.json``. Host-owned browser_scenarios
provide server argv, port and a fixed-step TaskSpec (up to ten scenarios, 64 KB each).
Every configured scenario is mandatory, even if the model does not reference it.
The application runs inside the offline container against read-only /work, never
a host shell. URLs use only that container's http://127.0.0.1:port (1024–65535).
Tasks are headless steps without environment secrets, bounded to 100 steps, 20
assertions, 120 seconds and 15 seconds per operation, within the worker's overall
deadline/output limits.

Trusted verifier code is snapshotted and mounted read-only at /trusted, separately
from edited /work and a read-only manifest. Application children do not inherit
the verifier import path. The Linux entry disables dumpability before starting the
application to block access to verifier memory and /proc output handles; failure
stops validation. Server output is not evidence. Servers/containers are cleaned up;
only redacted condition kinds/selectors and step/assertion counts are returned.
Real Podman acceptance is still required; host browser tests do not prove isolation.

Browser evidence binds tree, host scenario and trusted source digest. Changed
content/settings cannot reuse old evidence. The publisher rechecks all mandatory
checks/scenarios and condition counts; model finish cannot bypass them. The required
real local acceptance entry point includes the real browser container test and
fails when prerequisites are unavailable.

Intake quality, priority and history
------------------------------------------------------------

Preview/status triage shows task kind, classification basis, priority labels,
advisory suitability score and reasons. Kind uses type labels/title prefixes,
explicitly falling back to unknown; validated requirement analysis can classify
recorded outcomes. Scores do not grant tool permissions or predict success.
automation-manual/automation-blocked holds new jobs locally without claiming them.
Discovery refreshes a never-started held snapshot after labels are removed;
adding a hold during active execution cancels it.

priority_labels defaults to priority:critical/p0=100, priority:high/p1=75,
priority:normal/p2=50, priority:low/p3=25; unmatched jobs use 50. The highest matching
label wins; body text cannot raise priority or permissions. Hosts may configure up
to 50 labels scored 0–100. queue_aging_per_hour adds five points per waiting hour
by default (0 disables), with FIFO ties. Active work and pending reports precede
new admissions. Legacy queued jobs retain their snapshots and default to priority
50; ordinary queued requirements remain guarded before execution.
Discovery runs before selecting new work and refreshes queued priority labels so
new urgent issues do not wait for the entire old queue to drain. Priority refreshes
never replace ordinary admitted requirements.

.. code-block:: bash

    python -m je_web_runner.issue_worker metrics --config issue-worker.json --json
    python -m je_web_runner.issue_worker metrics --config issue-worker.json --since-hours 24 --report reports/issues
    python -m je_web_runner.issue_worker metrics --config issue-worker.json --issue github:123 --json

Metrics read local history only, without platforms/models. Reports include recorded
delivery rates by source/kind, measured duration/tools/validation rounds, failure
reasons, UTC daily trends and the latest 50 outcomes. Queue counts are current local
snapshots of holds, dependency/platform deferrals, pending reports and blocked
reviews; time windows filter outcomes only. --issue selects cross-retry/revision
history for a source issue.

Each run/revision is recorded once. Retry preserves old outcomes and report retries
do not inflate completion counts. Untracked legacy/write-failure observations are
reported separately and excluded from rates/timing; current state is never used to
invent history. Delivery does not mean business acceptance: business_acceptance is
not_measured. Metrics write failures cannot turn delivered PRs into failed issues.
SQLite upgrades add tables/columns/indexes; drain the old watch before upgrading.

--report writes matching JSON and standalone HTML with source filters and daily
bars, escaped text and no external assets/CDN. Python exposes
``IssueMetrics(store).summary()``/``write_report(base)`` and
``IssueWorker.metrics(since_hours=None, issue=None)``. MCP adds read-only
``webrunner_issue_metrics`` with optional since_hours/issue, using the frozen host
config. It never starts workers/writes platforms or accepts an output path.
