[CmdletBinding(SupportsShouldProcess)]
param([string]$Repository = (Split-Path -Parent $PSScriptRoot))
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path -LiteralPath $Repository).Path
$python = Join-Path $repo '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw 'Prepare the locked .venv with all dependency groups before registration.'
}
$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
$taskName = 'Clavis-Nightly-' + $identity.User.Value
$action = New-ScheduledTaskAction -Execute $python -Argument '-m training.jobs run --wait' -WorkingDirectory $repo
$trigger = New-ScheduledTaskTrigger -Daily -At '00:55'
$principal = New-ScheduledTaskPrincipal -UserId $identity.User.Value -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 7) -WakeToRun
$settings.DisallowStartIfOnBatteries = $true
$settings.StopIfGoingOnBatteries = $true
if ($PSCmdlet.ShouldProcess('Clavis nightly queue for current user', 'Register daily 00:55 task')) {
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description 'Clavis queue, local 01:00-07:00, AC only' -Force | Out-Null
    Write-Output 'Clavis nightly task registered; the user must remain signed in and the laptop powered on.'
}
