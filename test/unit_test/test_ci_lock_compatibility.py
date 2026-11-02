"""Universal CI pins must remain installable on the supported Python versions."""
from collections import defaultdict
from pathlib import Path
import re

from packaging.markers import default_environment
from packaging.requirements import Requirement
import pytest

LOCK = Path(__file__).resolve().parents[2] / ".github/requirements/ci.txt"


def _active_pins(version):
    environment = default_environment()
    environment.update(python_version=version, python_full_version=version + ".0")
    pins = defaultdict(list)
    for line in LOCK.read_text(encoding="utf-8").splitlines():
        if not re.match(r"^[A-Za-z0-9][A-Za-z0-9_.-]*(?:\[[^\]]+\])?==", line):
            continue
        requirement = Requirement(line.removesuffix("\\").strip())
        if requirement.marker is None or requirement.marker.evaluate(environment):
            pins[requirement.name].append(next(iter(requirement.specifier)).version)
    return pins


@pytest.mark.parametrize("version", ["3.11", "3.12", "3.13", "3.14"])
def test_supported_interpreters_select_one_version_per_distribution(version):
    assert all(len(versions) == 1 for versions in _active_pins(version).values())
