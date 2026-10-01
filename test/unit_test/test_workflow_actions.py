"""Every GitHub Actions step pins its action to a commit SHA.

A tag such as ``@v4`` can be moved to new code at any time (the 2025
tj-actions/changed-files compromise rewrote tags), so each ``uses:`` names a
full 40-hex commit and carries the release it corresponds to as a comment,
which is what Dependabot reads and updates. Pinning also keeps Node 20 actions
from lingering unnoticed: GitHub removed Node 20 from its runners on 2026-09-23.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_ROOT = next(p for p in Path(__file__).resolve().parents if (p / ".github" / "workflows").is_dir())
_WORKFLOWS = sorted((_ROOT / ".github" / "workflows").glob("*.yml"))
_USES = re.compile(r"^\s*(?:-\s*)?uses:\s*(\S+)(.*)$")
_PINNED = re.compile(r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$")
_LOCAL = re.compile(r"^\./")
_VERSION_COMMENT = re.compile(r"^\s+#\s*v\d+(\.\d+)*\s*$")


def _uses(path: Path) -> list[tuple[int, str, str]]:
    """Return ``(line number, action reference, rest of line)`` for each remote ``uses:``."""
    found = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        match = _USES.match(line)
        if match and not _LOCAL.match(match.group(1)):
            found.append((number, match.group(1), match.group(2)))
    return found


def test_workflows_exist():
    assert _WORKFLOWS  # nosec B101 — assert is the test assertion


@pytest.mark.parametrize("workflow", _WORKFLOWS, ids=lambda p: p.name)
def test_every_action_is_pinned_to_a_commit_with_its_version(workflow):
    bad = [f"{workflow.name}:{number} {ref}{rest}"
           for number, ref, rest in _uses(workflow)
           if not (_PINNED.match(ref) and _VERSION_COMMENT.match(rest))]
    assert bad == []  # nosec B101 — assert is the test assertion


def test_one_version_per_action():
    # The same action at two different commits means a partial upgrade.
    seen: dict[str, set[str]] = {}
    for workflow in _WORKFLOWS:
        for _number, ref, _rest in _uses(workflow):
            action, _, sha = ref.partition("@")
            seen.setdefault(action, set()).add(sha)
    assert {action: shas for action, shas in seen.items() if len(shas) > 1} == {}  # nosec B101 — assert is the test assertion


def test_dependabot_keeps_pins_current_on_dev():
    # Pinned SHAs only stay current if something bumps them; every update
    # goes to dev because main is the release branch. Parsed as text: PyYAML
    # is not a test dependency.
    text = (_ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
    blocks = re.split(r"^\s*-\s*package-ecosystem:", text, flags=re.MULTILINE)[1:]
    ecosystems = {block.split()[0].strip("\"'") for block in blocks}
    assert {"pip", "github-actions"} <= ecosystems  # nosec B101 — assert is the test assertion
    assert all(re.search(r"^\s*target-branch:\s*\"dev\"", block, re.MULTILINE)  # nosec B101 — assert is the test assertion
               for block in blocks)


def test_dependabot_waits_a_week_before_proposing_a_release():
    # A compromised release is usually found and yanked within days. Dependabot's
    # own default wait is 3 days, and zizmor's dependabot-cooldown audit asks
    # for 7. The wait never delays security updates.
    text = (_ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
    blocks = re.split(r"^\s*-\s*package-ecosystem:", text, flags=re.MULTILINE)[1:]
    days = [re.search(r"^\s*default-days:\s*(\d+)", block, re.MULTILINE) for block in blocks]
    assert blocks and all(match and int(match.group(1)) >= 7 for match in days)  # nosec B101 — assert is the test assertion


def _checkout_steps(path: Path) -> list[tuple[int, str]]:
    """Return ``(line number, step text)`` for each ``actions/checkout`` step."""
    lines = path.read_text(encoding="utf-8").splitlines()
    steps = []
    for index, line in enumerate(lines):
        if not re.search(r"uses:\s*actions/checkout@", line):
            continue
        column = line.index("uses:")
        body = [line]
        for following in lines[index + 1:]:
            indent = len(following) - len(following.lstrip())
            if following.strip() and (indent < column or following.lstrip().startswith("- ")):
                break
            body.append(following)
        steps.append((index + 1, "\n".join(body)))
    return steps


@pytest.mark.parametrize("workflow", _WORKFLOWS, ids=lambda p: p.name)
def test_every_checkout_decides_on_persisted_credentials(workflow):
    # actions/checkout leaves the job token in .git/config unless told not
    # to, where every later step (and any uploaded workspace) can read it.
    # Only jobs that push keep it, and they say so.
    bad = [f"{workflow.name}:{number}" for number, step in _checkout_steps(workflow)
           if not re.search(r"^\s*persist-credentials:\s*(true|false)\b", step, re.MULTILINE)]
    assert bad == []  # nosec B101 — assert is the test assertion


_JOB_HEAD = re.compile(r"^  [A-Za-z0-9_-]+:\s*(#.*)?$")


def _jobs(path: Path) -> list[tuple[str, str]]:
    """Return ``(job id, job text)`` for each job under ``jobs:`` in a workflow."""
    lines = path.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if re.match(r"^jobs:\s*(#.*)?$", line))
    heads = [i for i in range(start + 1, len(lines)) if _JOB_HEAD.match(lines[i])]
    ends = [*heads[1:], len(lines)]
    return [(lines[i].strip().rstrip(":"), "\n".join(lines[i:end])) for i, end in zip(heads, ends)]


@pytest.mark.parametrize("workflow", _WORKFLOWS, ids=lambda p: p.name)
def test_every_job_has_a_timeout(workflow):
    # Without timeout-minutes a hung job runs for GitHub's default six hours.
    # Each job sets about three times its slowest recent run, at least 15 minutes.
    bad = [name for name, body in _jobs(workflow)
           if "runs-on:" in body and not re.search(r"^\s*timeout-minutes:", body, re.MULTILINE)]
    assert bad == []  # nosec B101 — assert is the test assertion


_PIP_INSTALL = re.compile(r"\bpip3?\s+install\b[^\n]*")
_LOCKED_INSTALL = re.compile(
    r"^pip3? install --require-hashes --only-binary :all: -r \.github/requirements/[\w.-]+\.txt$")


def _token_jobs() -> list[tuple[str, str]]:
    """Return ``(workflow:job, job text)`` for each job that is handed the PyPI token."""
    return [(f"{workflow.name}:{name}", body) for workflow in _WORKFLOWS
            for name, body in _jobs(workflow) if "secrets.PYPI_API_TOKEN" in body]


def test_the_pypi_token_reaches_only_the_publish_jobs():
    expected = ['publish_stable.yml:publish', 'test_dev.yml:publish-dev']
    assert [name for name, _body in _token_jobs()] == expected  # nosec B101 — assert is the test assertion


@pytest.mark.parametrize("name, body", _token_jobs(), ids=[name for name, _body in _token_jobs()])
def test_a_job_with_the_pypi_token_installs_only_hash_locked_tooling(name, body):
    # A tool resolved when the job runs could change between two releases and read the token.
    installs = [match.group(0).strip() for match in _PIP_INSTALL.finditer(body)]
    assert installs, name  # nosec B101 — assert is the test assertion
    unlocked = [command for command in installs if not _LOCKED_INSTALL.match(command)]
    assert unlocked == [], name  # nosec B101 — assert is the test assertion


def test_dependabot_watches_the_hash_locked_requirements():
    # From "/" Dependabot does not look as deep as .github/requirements, so the
    # files CI installs with --require-hashes would never be updated.
    text = (_ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
    blocks = re.split(r"^\s*-\s*package-ecosystem:", text, flags=re.MULTILINE)[1:]
    pip_block = next(block for block in blocks if block.split()[0].strip("\"'") == "pip")
    watched = re.search(r'^\s*-\s*"/\.github/requirements"\s*$', pip_block, re.MULTILINE)
    assert watched  # nosec B101 — assert is the test assertion


_BUILD = re.compile(r"\bpython -m build\b[^\n]*")
_REQUIRES = re.compile(r'^requires\s*=\s*\[(?P<items>[^\]]*)\]', re.MULTILINE)


def _locked_version(package: str) -> tuple[int, ...]:
    """Return the version ``publish.txt`` pins for ``package`` as a tuple of numbers."""
    lock = (_ROOT / ".github" / "requirements" / "publish.txt").read_text(encoding="utf-8")
    version = re.search(rf"^{package}==([\d.]+)", lock, re.MULTILINE).group(1)
    return tuple(int(part) for part in version.split("."))


@pytest.mark.parametrize("name, body", _token_jobs(), ids=[name for name, _body in _token_jobs()])
def test_a_job_with_the_pypi_token_builds_with_the_locked_backend(name, body):
    # An isolated build downloads the newest setuptools each time, outside the lock.
    builds = _BUILD.findall(body)
    assert builds and all("--no-isolation" in command for command in builds), name  # nosec B101


@pytest.mark.parametrize("toml_name", ["pyproject.toml", "dev.toml"])
def test_the_locked_backend_satisfies_build_system_requires(toml_name):
    # --no-isolation checks the requirement instead of installing it, so a raised floor
    # (Dependabot edits pyproject.toml) must come with a regenerated lock.
    text = (_ROOT / toml_name).read_text(encoding="utf-8")
    items = re.findall(r'"([^"]+)"', _REQUIRES.search(text).group("items"))
    assert [re.split(r"[<>=!~ ]", item, maxsplit=1)[0] for item in items] == ["setuptools"]  # nosec B101
    floor = tuple(int(part) for part in re.search(r">=\s*([\d.]+)", items[0]).group(1).split("."))
    assert _locked_version("setuptools") >= floor  # nosec B101
