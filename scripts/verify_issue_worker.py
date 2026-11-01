"""Required real local acceptance; platform endpoints remain test fixtures, never live services."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys


def main() -> int:
    """Fail on missing prerequisites and run true local execution plus an optional long soak."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--soak-hours", type=float, default=24,
                        help="default 24; use 0 for end-to-end checks only (not full operational acceptance)")
    args = parser.parse_args()
    if not 0 <= args.soak_hours <= 168:
        parser.error("--soak-hours must be between 0 and 168")
    required = ("WEBRUNNER_ISSUE_MODEL", "WEBRUNNER_ISSUE_IMAGE")
    if not all(os.environ.get(name) for name in required):
        print("Required: WEBRUNNER_ISSUE_MODEL and WEBRUNNER_ISSUE_IMAGE; nothing was installed or started.",
              file=sys.stderr)
        return 1
    environment = dict(os.environ, WEBRUNNER_ISSUE_REAL_TESTS="1",
                       WEBRUNNER_ISSUE_SOAK_SECONDS=str(args.soak_hours * 3600))
    selected = "real_runtime or optional_real_podman"
    if not args.soak_hours:
        selected = "(" + selected + ") and not soak"
    command = [sys.executable, "-m", "pytest", "test/integration_test/test_issue_pipeline.py",
               "test/unit_test/test_issue_coding.py", "-q", "-s",
               "test/unit_test/test_issue_acceptance.py",
               "-k", selected, "--tb=short"]
    completed = subprocess.run(command, cwd=Path(__file__).resolve().parent.parent,  # nosec B603
                               env=environment, check=False)
    return completed.returncode


if __name__ == "__main__":
    sys.exit(main())
