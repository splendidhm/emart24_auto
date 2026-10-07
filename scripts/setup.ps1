param([Parameter(Mandatory=$true)][string]$Python)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $root
& $Python -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'venv creation failed' }
& "$root\.venv\Scripts\python.exe" -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'dependency installation failed' }
Write-Host 'Setup complete. Uses installed Microsoft Edge and Microsoft Excel.'
