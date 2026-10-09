[CmdletBinding(SupportsShouldProcess)]
param()
$ErrorActionPreference = 'Stop'
$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
$taskName = 'Clavis-Nightly-' + $identity.User.Value
if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
    if ($PSCmdlet.ShouldProcess('Clavis nightly queue for current user', 'Unregister task')) {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    }
}
