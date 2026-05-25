"""
SBOM (Software Bill of Materials) diff for PRs.

Reads CycloneDX 1.4+ JSON (the de-facto SBOM format Trivy / Syft / GitHub
Dependency Submission all emit) and reports:

* New components introduced by the PR.
* Removed components.
* Version bumps & downgrades.
* Newly-introduced licenses (helpful for AGPL / commercial guards).
* New components carrying a vulnerability list (if attached via CycloneDX
  ``vulnerabilities`` section).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

from je_web_runner.utils.exception.exceptions import WebRunnerException


class SbomDiffError(WebRunnerException):
    """Raised when SBOM input is malformed or thresholds are exceeded."""


@dataclass(frozen=True)
class Component:
    name: str
    version: str = ""
    purl: str = ""
    licenses: Tuple[str, ...] = ()

    @property
    def key(self) -> str:
        return self.purl or f"{self.name}@{self.version}"


@dataclass
class VersionChange:
    name: str
    base_version: str
    head_version: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SbomReport:
    added: List[Component] = field(default_factory=list)
    removed: List[Component] = field(default_factory=list)
    upgraded: List[VersionChange] = field(default_factory=list)
    downgraded: List[VersionChange] = field(default_factory=list)
    new_licenses: List[str] = field(default_factory=list)
    new_vulnerable: List[str] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(
            self.added or self.removed or self.upgraded
            or self.downgraded or self.new_licenses or self.new_vulnerable
        )


def _parse_components(sbom: Dict[str, Any]) -> List[Component]:
    if not isinstance(sbom, dict):
        raise SbomDiffError("sbom must be a dict")
    raw = sbom.get("components")
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise SbomDiffError("sbom.components must be a list")
    out: List[Component] = []
    for c in raw:
        if not isinstance(c, dict):
            continue
        name = c.get("name")
        if not isinstance(name, str) or not name:
            continue
        licenses = []
        for lic in c.get("licenses") or []:
            if isinstance(lic, dict):
                inner = lic.get("license") or {}
                lid = inner.get("id") or inner.get("name") or lic.get("expression")
                if isinstance(lid, str):
                    licenses.append(lid)
        out.append(Component(
            name=name,
            version=str(c.get("version") or ""),
            purl=str(c.get("purl") or ""),
            licenses=tuple(licenses),
        ))
    return out


def _vulnerable_purls(sbom: Dict[str, Any]) -> set:
    vulns = sbom.get("vulnerabilities")
    if not isinstance(vulns, list):
        return set()
    refs: set = set()
    for v in vulns:
        if not isinstance(v, dict):
            continue
        for affect in v.get("affects") or []:
            ref = affect.get("ref") if isinstance(affect, dict) else None
            if isinstance(ref, str):
                refs.add(ref)
    return refs


def _index(components: Iterable[Component]) -> Dict[str, Component]:
    return {c.key: c for c in components}


def _version_order(a: str, b: str) -> Optional[int]:
    """Return -1/0/1 if version sort is decidable, None otherwise."""
    if a == b:
        return 0
    try:
        ta = tuple(int(p) for p in a.replace("-", ".").split(".") if p.isdigit())
        tb = tuple(int(p) for p in b.replace("-", ".").split(".") if p.isdigit())
    except ValueError:
        return None
    if not ta or not tb:
        return None
    if ta < tb:
        return -1
    if ta > tb:
        return 1
    return 0


def diff_sboms(base: Dict[str, Any], head: Dict[str, Any]) -> SbomReport:
    """Compare two CycloneDX SBOMs and return a high-level report."""
    base_comps = _parse_components(base)
    head_comps = _parse_components(head)
    base_idx = _index(base_comps)
    head_idx = _index(head_comps)

    base_names = {c.name: c for c in base_comps}
    head_names = {c.name: c for c in head_comps}
    base_keys = set(base_idx)
    head_keys = set(head_idx)

    same_name_keys = {
        c.key for c in head_comps
        if c.name in base_names and c.key not in base_keys
    }
    treat_as_added_keys = (head_keys - base_keys) - same_name_keys
    treat_as_removed_keys = (base_keys - head_keys) - {
        base_names[name].key for name in head_names if name in base_names
    }

    report = SbomReport(
        added=[head_idx[k] for k in sorted(treat_as_added_keys)],
        removed=[base_idx[k] for k in sorted(treat_as_removed_keys)],
    )

    for name, head_c in head_names.items():
        if name not in base_names:
            continue
        base_c = base_names[name]
        if base_c.version == head_c.version:
            continue
        order = _version_order(base_c.version, head_c.version)
        change = VersionChange(name=name,
                               base_version=base_c.version,
                               head_version=head_c.version)
        if order == -1:
            report.upgraded.append(change)
        elif order == 1:
            report.downgraded.append(change)
        else:
            report.upgraded.append(change)  # unknown order → treat as change

    base_licenses = {l for c in base_comps for l in c.licenses}
    head_licenses = {l for c in head_comps for l in c.licenses}
    report.new_licenses = sorted(head_licenses - base_licenses)

    head_vuln_purls = _vulnerable_purls(head)
    base_vuln_purls = _vulnerable_purls(base)
    new_vuln_refs = head_vuln_purls - base_vuln_purls
    report.new_vulnerable = sorted(new_vuln_refs)

    return report


def assert_no_new_vulnerable(report: SbomReport) -> None:
    if report.new_vulnerable:
        raise SbomDiffError(
            f"PR introduces vulnerable components: {report.new_vulnerable}"
        )


def assert_no_disallowed_licenses(
    report: SbomReport, disallowed: Iterable[str],
) -> None:
    disallowed_set = {l.upper() for l in disallowed}
    if not disallowed_set:
        raise SbomDiffError("disallowed list must be non-empty")
    bad = [l for l in report.new_licenses if l.upper() in disallowed_set]
    if bad:
        raise SbomDiffError(f"PR introduces disallowed licenses: {bad}")


def report_markdown(report: SbomReport) -> str:
    if not isinstance(report, SbomReport):
        raise SbomDiffError("report must be SbomReport")
    lines = ["## SBOM diff"]
    if not report.has_changes:
        lines.append("_No changes._")
        return "\n".join(lines)
    if report.added:
        lines.append(f"### Added ({len(report.added)})")
        lines.extend(f"- `{c.name}@{c.version}`" for c in report.added)
    if report.removed:
        lines.append(f"### Removed ({len(report.removed)})")
        lines.extend(f"- `{c.name}@{c.version}`" for c in report.removed)
    if report.upgraded:
        lines.append(f"### Upgraded ({len(report.upgraded)})")
        lines.extend(
            f"- `{c.name}` {c.base_version} → {c.head_version}"
            for c in report.upgraded
        )
    if report.downgraded:
        lines.append(f"### Downgraded ({len(report.downgraded)})")
        lines.extend(
            f"- `{c.name}` {c.base_version} → {c.head_version}"
            for c in report.downgraded
        )
    if report.new_licenses:
        lines.append("### New licenses")
        lines.append(", ".join(f"`{l}`" for l in report.new_licenses))
    if report.new_vulnerable:
        lines.append("### New vulnerable components")
        lines.extend(f"- `{ref}`" for ref in report.new_vulnerable)
    return "\n".join(lines)
