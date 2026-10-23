"""Dedicated clone/worktrees and verified textual patches; never edit the live checkout."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from je_web_runner.utils.issue_worker.policy import checked_path, preserve_tests
from je_web_runner.utils.issue_worker.types import IssueWorkerConfig, IssueWorkerError


def git_run(directory: Path, arguments: list[str], timeout: float = 30) -> str:
    """Run fixed git argv with hooks/global config disabled and no inherited credentials."""
    env = {name: value for name, value in os.environ.items()
           if name.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PATHEXT"}}
    env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_TERMINAL_PROMPT": "0"})
    result = subprocess.run(  # nosec B603 B607
        ["git", "-c", "core.hooksPath=" + str(directory / ".disabled-hooks"), "-C", str(directory), *arguments],
        env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=max(0.001, timeout),
        check=False,
    )
    if result.returncode:
        raise IssueWorkerError("git operation failed: " + arguments[0])
    return result.stdout


class IssueWorkspace:
    """An explicitly owned worktree and its immutable baseline commit."""

    def __init__(self, root: Path, base_sha: str, config: IssueWorkerConfig) -> None:
        self.root = root.resolve()
        self.base_sha = base_sha
        self.config = config

    @classmethod
    def prepare(cls, config: IssueWorkerConfig, job: dict[str, Any], remote: str | None = None) -> IssueWorkspace:
        """Create or reopen a private clone/worktree; remote injection is a Python test seam only."""
        state = Path(config.state_dir).resolve()
        state.mkdir(parents=True, exist_ok=True)
        clone = state / "repository"
        if not clone.exists():
            git_run(state, ["clone", "--no-checkout", "--", remote or f"https://github.com/{config.repository}.git",
                            str(clone)], timeout=120)
        slug = job["key"].replace(":", "-") + f"-r{job['run']}"
        root = state / "worktrees" / slug
        saved = job["data"].get("base_sha")
        if root.exists():
            if not saved:
                saved = git_run(root, ["rev-parse", "HEAD"]).strip()
            return cls(root, saved, config)
        root.parent.mkdir(parents=True, exist_ok=True)
        git_run(clone, ["fetch", "origin", config.base_branch], timeout=120)
        base = saved or git_run(clone, ["rev-parse", "FETCH_HEAD"]).strip()
        git_run(clone, ["worktree", "add", "--detach", str(root), base])
        return cls(root, base, config)

    def files(self) -> list[str]:
        """List indexed paths, including staged new files and excluding the git database."""
        return [name for name in git_run(self.root, ["ls-files", "-z"]).split("\0") if name]

    def read(self, name: str) -> str:
        """Read a bounded UTF-8 regular file, following no symlinks."""
        target = checked_path(self.root, name)
        if not target.is_file() or target.stat().st_size > 200_000:
            raise IssueWorkerError("file is absent or exceeds the coding read limit")
        try:
            return target.read_text(encoding="utf-8")[:16000]
        except UnicodeError as error:
            raise IssueWorkerError("coding tools only read UTF-8 text files") from error

    def search(self, text: str) -> list[dict[str, Any]]:
        """Literal search in bounded, readable indexed files; no shell or regex evaluation."""
        matches = []
        for name in self.files():
            try:
                content = self.read(name)
            except IssueWorkerError:
                continue  # excluded credentials, binary/large files are intentionally not searchable
            for number, line in enumerate(content.splitlines(), 1):
                if text in line:
                    matches.append({"path": name, "line": number, "text": line[:300]})
                    if len(matches) >= 40:
                        return matches
        return matches

    def _numstat(self, arguments: list[str]) -> list[tuple[int, int, str]]:
        stats = []
        for row in git_run(self.root, arguments).split("\0"):
            if not row:
                continue
            fields = row.split("\t", 2)
            if len(fields) != 3 or not fields[0].isdigit() or not fields[1].isdigit() or not fields[2]:
                raise IssueWorkerError("binary patches and rename syntax are not accepted; use text delete/add")
            checked_path(self.root, fields[2], write=True)
            stats.append((int(fields[0]), int(fields[1]), fields[2]))
        return stats

    def changes(self) -> list[tuple[int, int, str]]:
        """Authoritative cumulative changes relative to the recorded baseline."""
        return self._numstat(["diff", "--cached", "--no-renames", "--numstat", "-z", self.base_sha])

    def patch(self, patch: str) -> list[str]:
        """Check and apply a bounded unified diff, restoring the prior index on policy failure."""
        if len(patch.encode()) > 500_000 or "GIT binary patch" in patch:
            raise IssueWorkerError("patch exceeds the text patch limit")
        patch_file = self.root.parent / (self.root.name + ".patch")
        patch_file.write_text(patch.replace("\r\n", "\n"), encoding="utf-8", newline="\n")
        stats = self._numstat(["apply", "--numstat", "-z", str(patch_file)])
        before = {name: self._base_text(name) for _added, _removed, name in stats if name.startswith("test/")}
        tree = git_run(self.root, ["write-tree"]).strip()
        git_run(self.root, ["apply", "--check", "--index", "--", str(patch_file)])
        git_run(self.root, ["apply", "--index", "--", str(patch_file)])
        try:
            self.verify_scope()
            for name, original in before.items():
                target = checked_path(self.root, name, write=True)
                if name.endswith(".py"):
                    preserve_tests(original, target.read_text(encoding="utf-8") if target.exists() else "")
        except Exception:
            git_run(self.root, ["read-tree", "--reset", "-u", tree])
            raise
        return [name for _added, _removed, name in stats]

    def _base_text(self, name: str) -> str:
        try:
            return git_run(self.root, ["show", self.base_sha + ":" + name])
        except IssueWorkerError:
            return ""  # new tests have no baseline content

    def verify_scope(self) -> None:
        """Enforce cumulative file/line/mode limits and reject partial unstaged edits."""
        changes = self.changes()
        if len(changes) > self.config.max_files or sum(a + d for a, d, _name in changes) > self.config.max_lines:
            raise IssueWorkerError("cumulative patch exceeds host file/line limits")
        for line in git_run(self.root, ["ls-files", "--stage"]).splitlines():
            if line.split()[0] not in {"100644", "100755"}:
                raise IssueWorkerError("symlinks and submodules are not supported in worker snapshots")
        if git_run(self.root, ["diff", "--name-only"]):
            raise IssueWorkerError("worktree has unstaged changes outside the validated patch")

    def fingerprint(self) -> str:
        """A tree ID pins check results to exactly the content later published."""
        return git_run(self.root, ["write-tree"]).strip()

    def export(self, destination: Path) -> None:
        """Copy only indexed source, never .git, credential files or host configuration."""
        destination.mkdir(parents=True, exist_ok=False)
        for name in self.files():
            try:
                source = checked_path(self.root, name)
            except IssueWorkerError:
                continue  # credential paths are deliberately excluded from test containers
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
