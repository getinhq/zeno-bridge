$ErrorActionPreference = "Stop"

$Python = $env:PYTHON_BIN
if (-not $Python) {
  $Python = (Get-Command python -ErrorAction SilentlyContinue)?.Source
}
if (-not $Python) {
  throw "Python not found. Install Python 3.10+ and add to PATH."
}

$TaskName = "ZenoBridgeDaemon"
$Action = New-ScheduledTaskAction -Execute $Python -Argument "-m zeno_bridge.daemon"
$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel LeastPrivilege
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 0)

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName
Write-Host "Installed and started task: $TaskName"
