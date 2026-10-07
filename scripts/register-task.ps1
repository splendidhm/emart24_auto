param([string]$Config = 'config.json')
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$cfgPath = if ([IO.Path]::IsPathRooted($Config)) { [IO.Path]::GetFullPath($Config) } else { [IO.Path]::GetFullPath((Join-Path $root $Config)) }
$python = Join-Path $root '.venv\Scripts\python.exe'
# Production import must have completed or confirmed an existing batch.
Push-Location -LiteralPath $root
try {
    & $python -m emart24 --config $cfgPath check-ready
    if ($LASTEXITCODE -ne 0) { throw 'Complete site verification and one validated production import before registration.' }
    # Use exactly the same resolved configuration as manual and scheduled runs.
    # ASCII JSON avoids Windows PowerShell 5.1 native UTF-8/code-page mismatch.
    $configOutput = & $python -m emart24 --config $cfgPath show-config --ascii
    if ($LASTEXITCODE -ne 0) { throw 'Configuration could not be loaded.' }
    $cfg = ($configOutput -join "`n") | ConvertFrom-Json
} finally { Pop-Location }
if ((Get-TimeZone).Id -ne 'Korea Standard Time') { throw 'Windows time zone must be Korea Standard Time.' }
$action = New-ScheduledTaskAction -Execute $python -Argument ('-m emart24 --config "' + $cfgPath + '" run --scheduled') -WorkingDirectory $root
$daily = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At $cfg.start
$identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$login = New-ScheduledTaskTrigger -AtLogOn -User $identity
$principal = New-ScheduledTaskPrincipal -UserId $identity -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 45)
Register-ScheduledTask -TaskName 'Emart24-CJ-DailyImport' -Action $action -Trigger @($daily,$login) -Principal $principal -Settings $settings -Description 'CJ orders, weekdays 10:30 KST; retry until 11:00.' -Force
