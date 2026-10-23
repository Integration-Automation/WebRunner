"""Exercise the real PowerShell task script with intercepted OS calls; live registration is opt-in."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/issue_worker_task.ps1"
POWERSHELL = shutil.which("powershell.exe")
pytestmark = pytest.mark.skipif(os.name != "nt" or not POWERSHELL, reason="Windows PowerShell required")

HARNESS = r'''
param($TaskScript, $ConfigFile, $PythonFile, $Mode)
$global:taskCaptured = @{}
function Get-ScheduledTask {
    param($TaskName, $ErrorAction)
    if ($env:WEBRUNNER_TASK_TEST_EXISTING -eq 'foreign') {
        return [pscustomobject]@{ Description = 'different owner'; State = 'Ready' }
    }
    return $null
}
function New-ScheduledTaskAction {
    param($Execute, $Argument, $WorkingDirectory)
    $global:taskCaptured.action = $PSBoundParameters
    return [pscustomobject]@{ Kind = 'action' }
}
function New-ScheduledTaskTrigger {
    param([switch]$AtLogOn, $User)
    $global:taskCaptured.trigger = $PSBoundParameters
    return [pscustomobject]@{ Kind = 'trigger' }
}
function New-ScheduledTaskPrincipal {
    param($UserId, $LogonType, $RunLevel)
    $global:taskCaptured.principal = $PSBoundParameters
    return [pscustomobject]@{ Kind = 'principal' }
}
function New-ScheduledTaskSettingsSet {
    param($MultipleInstances, $RestartCount, $RestartInterval, $ExecutionTimeLimit,
          [switch]$StartWhenAvailable, [switch]$Hidden, [switch]$AllowStartIfOnBatteries,
          [switch]$DontStopIfGoingOnBatteries)
    $global:taskCaptured.settings = @{
        MultipleInstances = $MultipleInstances; RestartCount = $RestartCount
        RestartSeconds = $RestartInterval.TotalSeconds; LimitSeconds = $ExecutionTimeLimit.TotalSeconds
        Hidden = $Hidden.IsPresent
    }
    return [pscustomobject]@{ Kind = 'settings' }
}
function Register-ScheduledTask {
    param($TaskName, $Description, $Action, $Trigger, $Principal, $Settings, [switch]$Force)
    $global:taskCaptured.name = $TaskName
    return [pscustomobject]@{ TaskName = $TaskName; State = 'Ready' }
}
function Start-Process {
    param($FilePath, $ArgumentList, $WindowStyle, $WorkingDirectory, [switch]$Wait, [switch]$PassThru)
    @{ executable=$FilePath; arguments=$ArgumentList; window=$WindowStyle; working=$WorkingDirectory } |
        ConvertTo-Json -Compress | Write-Host
    return [pscustomobject]@{ ExitCode = 7 }
}
& $TaskScript -Action $Mode -Config $ConfigFile -Python $PythonFile | Out-Null
if ($Mode -eq 'Run') { exit $LASTEXITCODE }
$global:taskCaptured | ConvertTo-Json -Depth 6 -Compress
'''


def invoke(tmp_path, mode="Install", foreign=False):
    config = tmp_path / "設定 with spaces.json"
    config.write_text("{}", encoding="utf-8")
    harness = tmp_path / "task-harness.ps1"
    harness.write_text(HARNESS, encoding="utf-8-sig")
    environment = dict(os.environ, WEBRUNNER_TASK_TEST_EXISTING="foreign" if foreign else "")
    return subprocess.run([POWERSHELL, "-NoProfile", "-NonInteractive", "-File", str(harness),
                           str(SCRIPT), str(config), sys.executable, mode], capture_output=True,
                          encoding="utf-8", errors="replace", env=environment, timeout=20, check=False)


def test_task_registration_policy_and_quoted_paths(tmp_path):
    result = invoke(tmp_path)
    assert result.returncode == 0, result.stderr
    captured = json.loads(result.stdout)
    assert captured["principal"]["LogonType"] == "Interactive"
    assert captured["principal"]["RunLevel"] == "Limited"
    assert captured["settings"] == {"MultipleInstances": "IgnoreNew", "RestartCount": 3,
                                    "RestartSeconds": 60, "LimitSeconds": 0, "Hidden": True}
    assert '-WindowStyle Hidden -File "' in captured["action"]["Argument"]
    assert 'with spaces.json"' in captured["action"]["Argument"]
    assert captured["name"].startswith("WebRunner-IssueWorker-")


def test_task_collision_refuses_to_modify_another_owner(tmp_path):
    result = invoke(tmp_path, foreign=True)
    assert result.returncode != 0
    assert "different owner" in result.stderr


def test_task_run_propagates_child_exit_and_hides_window(tmp_path):
    result = invoke(tmp_path, mode="Run")
    # The script's exit terminates the harness; the intercepted Start-Process is the only output.
    assert result.returncode == 7, result.stderr
    assert json.loads(result.stdout)["window"] == "Hidden"


def test_optional_live_task_registration_and_removal(tmp_path):
    if os.environ.get("WEBRUNNER_TEST_SCHEDULER") != "1":
        pytest.skip("set WEBRUNNER_TEST_SCHEDULER=1 to register/remove a unique temporary Windows task")
    config = tmp_path / "worker.json"
    config.write_text("{}", encoding="utf-8")
    base = [POWERSHELL, "-NoProfile", "-NonInteractive", "-File", str(SCRIPT),
            "-Config", str(config), "-Python", sys.executable]
    try:
        installed = subprocess.run([*base, "-Action", "Install"], capture_output=True,
                                   timeout=30, check=False)
        assert installed.returncode == 0, installed.stderr
        status = subprocess.run([*base, "-Action", "Status"], capture_output=True, timeout=30, check=False)
        assert status.returncode == 0 and b"WebRunner-IssueWorker-" in status.stdout
    finally:
        removed = subprocess.run([*base, "-Action", "Remove"], capture_output=True, timeout=30, check=False)
        assert removed.returncode == 0, removed.stderr
