param([string]$Config = 'config.json')
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$cfgPath = [IO.Path]::GetFullPath((Join-Path $root $Config))
$cfg = Get-Content -LiteralPath $cfgPath -Raw -Encoding UTF8 | ConvertFrom-Json
$runtime = if ([IO.Path]::IsPathRooted($cfg.runtime)) { $cfg.runtime } else { Join-Path (Split-Path $cfgPath -Parent) $cfg.runtime }
$stampPath = Join-Path $runtime 'site_verified.json'
if (-not (Test-Path -LiteralPath $stampPath)) { throw 'Run verify-site successfully before registration.' }
$stamp = Get-Content -LiteralPath $stampPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($stamp.config_hash -ne (Get-FileHash -LiteralPath $cfgPath -Algorithm SHA256).Hash.ToLower()) { throw 'Configuration changed. Run verify-site again.' }
$python = Join-Path $root '.venv\Scripts\python.exe'
# Production import must have completed or confirmed an existing batch.
Push-Location -LiteralPath $root
try { & $python -m emart24 --config $cfgPath check-ready } finally { Pop-Location }
if ($LASTEXITCODE -ne 0) { throw 'Complete one validated production import before registration.' }
if ((Get-TimeZone).Id -ne 'Korea Standard Time') { throw 'Windows time zone must be Korea Standard Time.' }
$action = New-ScheduledTaskAction -Execute $python -Argument ('-m emart24 --config "' + $cfgPath + '" run --scheduled') -WorkingDirectory $root
$daily = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At $cfg.start
$identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$login = New-ScheduledTaskTrigger -AtLogOn -User $identity
$principal = New-ScheduledTaskPrincipal -UserId $identity -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 45)
Register-ScheduledTask -TaskName 'Emart24-CJ-DailyImport' -Action $action -Trigger @($daily,$login) -Principal $principal -Settings $settings -Description 'CJ orders, weekdays 10:30 KST; retry until 11:00.' -Force
