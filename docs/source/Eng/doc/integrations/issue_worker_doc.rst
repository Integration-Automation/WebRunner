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
