<#
.SYNOPSIS
Manage a per-user, login-triggered issue worker. No credentials are stored in the task.
#>
[CmdletBinding()]
param(
    [ValidateSet('Install', 'Start', 'Status', 'Remove', 'Run')]
    [string]$Action = 'Status',
    [Parameter(Mandatory = $true)]
    [string]$Config,
    [string]$Python = (Join-Path $PSScriptRoot '../.venv/Scripts/python.exe')
)

$ErrorActionPreference = 'Stop'
$configPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Config)
$pythonPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Python)
$scriptPath = (Resolve-Path -LiteralPath $PSCommandPath).ProviderPath
foreach ($inputPath in @($configPath, $pythonPath, $scriptPath)) {
    if ($inputPath -match '["\r\n]') {
        throw 'Paths must not contain quotes or line breaks.'
    }
}
if ($Action -in @('Install', 'Run')) {
    foreach ($requiredPath in @($configPath, $pythonPath)) {
        if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
            throw 'Install and Run require existing config and Python files.'
        }
    }
}

if ($Action -eq 'Run') {
    # Start-Process joins ArgumentList; explicitly quote the absolute config filename.
    $arguments = @('-m', 'je_web_runner.issue_worker', 'watch', '--config', ('"' + $configPath + '"'))
    $process = Start-Process -FilePath $pythonPath -ArgumentList $arguments -WindowStyle Hidden `
        -WorkingDirectory (Split-Path -Parent $PSScriptRoot) -Wait -PassThru
    exit $process.ExitCode
}

$digest = [System.Security.Cryptography.SHA256]::Create()
try {
    $configHash = ([System.BitConverter]::ToString(
        $digest.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($configPath.ToLowerInvariant()))
    )).Replace('-', '').Substring(0, 16)
} finally {
    $digest.Dispose()
}
$taskName = 'WebRunner-IssueWorker-' + $configHash
$description = 'WebRunner owned issue worker: ' + $configHash
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing -and $existing.Description -ne $description) {
    throw 'The task name belongs to a different owner; refusing to change it.'
}

switch ($Action) {
    'Install' {
        if ($existing -and $existing.State -eq 'Running') {
            throw 'Drain the running worker before updating its task.'
        }
        $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
        $taskArguments = '-NoProfile -NonInteractive -WindowStyle Hidden -File "' + $scriptPath +
            '" -Action Run -Config "' + $configPath + '" -Python "' + $pythonPath + '"'
        $powershellPath = Join-Path $env:SystemRoot 'System32/WindowsPowerShell/v1.0/powershell.exe'
        $taskAction = New-ScheduledTaskAction -Execute $powershellPath `
            -Argument $taskArguments -WorkingDirectory (Split-Path -Parent $PSScriptRoot)
        $trigger = New-ScheduledTaskTrigger -AtLogOn -User $identity
        $principal = New-ScheduledTaskPrincipal -UserId $identity -LogonType Interactive -RunLevel Limited
        $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -RestartCount 3 `
            -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) `
            -StartWhenAvailable -Hidden -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
        Register-ScheduledTask -TaskName $taskName -Description $description -Action $taskAction `
            -Trigger $trigger -Principal $principal -Settings $settings -Force | Select-Object TaskName, State
    }
    'Start' {
        if (-not $existing) { throw 'Install the task first.' }
        Start-ScheduledTask -TaskName $taskName
    }
    'Status' {
        if ($existing) {
            $existing | Select-Object TaskName, State
            Get-ScheduledTaskInfo -TaskName $taskName | Select-Object LastRunTime, LastTaskResult, NextRunTime
        } else {
            Write-Output 'Task is not installed.'
        }
    }
    'Remove' {
        if ($existing -and $existing.State -eq 'Running') {
            throw 'Use the issue worker stop command and wait for it to drain before removing the task.'
        }
        if ($existing) { Unregister-ScheduledTask -TaskName $taskName -Confirm:$false }
    }
}
