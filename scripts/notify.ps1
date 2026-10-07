param([string]$Message)
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$icon = New-Object System.Windows.Forms.NotifyIcon
try {
    $icon.Icon = [System.Drawing.SystemIcons]::Information
    $icon.Visible = $true
    $icon.ShowBalloonTip(10000, 'Emart24', $Message, [System.Windows.Forms.ToolTipIcon]::Info)
    Start-Sleep -Seconds 12
} finally { $icon.Dispose() }
