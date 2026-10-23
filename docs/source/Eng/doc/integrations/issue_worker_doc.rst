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
