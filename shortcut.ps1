param([switch]$Startup, [switch]$Status, [switch]$Desktop, [string]$PythonPath)
$ErrorActionPreference = 'Stop'
$appRoot = $PSScriptRoot
$pythonPath = if ($PythonPath) { $PythonPath } else { (Get-Command python.exe).Source }
$pythonwPath = Join-Path (Split-Path $pythonPath) 'pythonw.exe'
if (-not (Test-Path -LiteralPath $pythonwPath)) { throw 'pythonw.exe was not found' }
$destination = if ($Startup) { [Environment]::GetFolderPath('Startup') } elseif ($Desktop) { [Environment]::GetFolderPath('Desktop') } else { $appRoot }
$shortcutPath = Join-Path $destination 'Quota Glance.lnk'
$wsh = New-Object -ComObject WScript.Shell
$link = $wsh.CreateShortcut($shortcutPath)
if ($Status) {
    $expectedArgs = '"' + (Join-Path $appRoot 'launch.py') + '" --startup'
    $disabled = $false
    foreach ($hive in @('HKCU:', 'HKLM:')) {
        $approvalPath = "$hive\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\StartupFolder"
        $approval = Get-ItemProperty -LiteralPath $approvalPath -Name 'Quota Glance.lnk' -ErrorAction SilentlyContinue
        if ($approval -and $approval.'Quota Glance.lnk' -and $approval.'Quota Glance.lnk'[0] -in @(3,7)) { $disabled = $true }
    }
    $valid = (Test-Path -LiteralPath $shortcutPath) -and ($link.TargetPath -eq $pythonwPath) -and ($link.Arguments -eq $expectedArgs) -and ($link.WorkingDirectory -eq $appRoot) -and (Test-Path -LiteralPath (Join-Path $appRoot 'launch.py'))
    @{ enabled = ($valid -and -not $disabled); valid = $valid; disabled = $disabled } | ConvertTo-Json -Compress
    exit
}
$link.TargetPath = $pythonwPath
$link.Arguments = '"' + (Join-Path $appRoot 'launch.py') + '"' + $(if ($Startup) { ' --startup' } else { '' })
$link.WorkingDirectory = $appRoot
$link.Description = 'AI account usage monitor'
$link.IconLocation = (Join-Path $appRoot 'assets\quota-glance.ico') + ',0'
$link.Save()
Write-Output $shortcutPath
