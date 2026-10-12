param([string]$Config = 'config.json', [datetime]$StartDate = (Get-Date).Date)
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
$startTime = [datetime]::ParseExact($cfg.start,'HH:mm',[Globalization.CultureInfo]::InvariantCulture)
$endTime = [datetime]::ParseExact($cfg.deadline,'HH:mm',[Globalization.CultureInfo]::InvariantCulture)
if ($endTime -lt $startTime -or [int]$cfg.retry_seconds -ne 300) { throw 'Invalid collection window.' }
$daily = @()
for ($slot = $startTime; $slot -le $endTime; $slot = $slot.AddMinutes(5)) {
    $daily += New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday,Saturday -At ($StartDate.Date.Add($slot.TimeOfDay))
}
$identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$login = New-ScheduledTaskTrigger -AtLogOn -User $identity
$login.StartBoundary = $StartDate.Date.ToString('yyyy-MM-ddTHH:mm:ss')
$principal = New-ScheduledTaskPrincipal -UserId $identity -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 45)
Register-ScheduledTask -TaskName 'Emart24-CJ-DailyImport' -Action $action -Trigger @($daily + @($login)) -Principal $principal -Settings $settings -Description 'CJ orders, Mon-Sat every 5 minutes 10:40-11:10 KST; all valid transfers; ambiguous revisions require review.' -Force
