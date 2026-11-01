"""Offline browser validation using trusted verifier code mounted separately from edited source."""
from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import secrets
import subprocess
import tempfile
from typing import Any

from je_web_runner.utils.issue_worker.browser_contract import scenario_task
from je_web_runner.utils.issue_worker.sandbox import PodmanSandbox
from je_web_runner.utils.issue_worker.types import EnvironmentUnavailable, IssueWorkerConfig, IssueWorkerError
from je_web_runner.utils.issue_worker.workspace import IssueWorkspace

_RESULT_MARKER = "WEBRUNNER_BROWSER_RESULT="


class BrowserAcceptance:
    """Every configured scenario is mandatory; models cannot weaken or replace these assertions."""

    def __init__(self, config: IssueWorkerConfig) -> None:
        self.config = config
        self.package = Path(__file__).resolve().parents[2]
        self.sources = {path.relative_to(self.package): path.read_bytes()
                        for path in sorted(self.package.rglob("*.py"))
                        if not path.is_symlink() and path.resolve().is_relative_to(self.package)}
        digest = hashlib.sha256()
        for name, content in self.sources.items():
            digest.update(name.as_posix().encode())
            digest.update(content)
        self.verifier_hash = digest.hexdigest()

    def signature(self, name: str) -> str:
        """Pin cached evidence to both host assertions and trusted verifier source."""
        if name not in self.config.browser_scenarios:
            raise IssueWorkerError("unknown host browser scenario")
        payload = [self.config.browser_scenarios[name], self.verifier_hash]
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    def check(self, workspace: IssueWorkspace, name: str, timeout: float) -> dict[str, Any]:
        """Reuse the offline Podman policy; mount no host credentials or writable source."""
        signature = self.signature(name)
        case = self.config.browser_scenarios[name]
        scenario_task(case)
        workspace.verify_scope()
        tree = workspace.fingerprint()
        command = ["python", "/trusted/entry.py", "/manifest/plan.json"]
        settings = replace(self.config, checks={"browser": command})
        sandbox = PodmanSandbox(settings)
        with tempfile.TemporaryDirectory(prefix="webrunner-browser-check-") as temporary:
            root = Path(temporary)
            source = root / "source"
            workspace.export(source)
            self._trusted_bundle(root / "trusted")
            manifest = root / "plan.json"
            manifest.write_text(json.dumps({"case": case, "tree": tree, "signature": signature}), encoding="utf-8")
            container = "webrunner-issue-" + secrets.token_hex(12)
            argv = sandbox.argv(workspace, "browser", source, container)
            image_position = argv.index(settings.image)
            for path, destination in ((root / "trusted", "/trusted"), (manifest, "/manifest/plan.json")):
                mount = f"type=bind,src={path},destination={destination},ro=true"
                argv[image_position:image_position] = ["--mount", mount]
                image_position += 2
            argv[argv.index("PYTHONPATH=/work")] = "PYTHONPATH=/trusted"
            try:
                result = sandbox._execute(argv, container, root / "output.log", timeout)
            except (OSError, subprocess.SubprocessError) as error:
                raise EnvironmentUnavailable("browser container infrastructure is unavailable") from error
            if result.get("exit_code") in {125, 126, 127}:
                raise EnvironmentUnavailable("browser container could not start")
        evidence = self._evidence(result.get("output", ""), tree, signature)
        passed = result.get("passed") is True and evidence.get("status") == "success" and \
            evidence.get("conditions_verified") == len(case["task"]["success"])
        return {"name": name, "tree": tree, "signature": signature, "passed": passed,
                "output": result.get("output", ""), "evidence": evidence}

    def _trusted_bundle(self, destination: Path) -> None:
        for name, content in self.sources.items():
            target = destination / "je_web_runner" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        (destination / "entry.py").write_bytes(self.sources[Path("utils/issue_worker/browser_entry.py")])

    @staticmethod
    def _evidence(output: str, tree: str, signature: str) -> dict[str, Any]:
        for line in reversed(output.splitlines()):
            if not line.startswith(_RESULT_MARKER):
                continue
            try:
                evidence = json.loads(line[len(_RESULT_MARKER):])
            except (ValueError, TypeError):
                break
            if isinstance(evidence, dict) and evidence.get("tree") == tree and evidence.get("signature") == signature:
                return evidence
            break
        return {"status": "failed", "stopped_reason": "missing or mismatched trusted browser evidence"}
