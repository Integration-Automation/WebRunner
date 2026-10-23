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
pending platform delivery return 1. Ctrl-C returns 130. Retry is explicit: restore
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
