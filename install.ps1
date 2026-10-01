param([string]$PythonPath, [switch]$NoLaunch, [switch]$NoShortcuts, [switch]$CheckOnly)
$ErrorActionPreference = 'Stop'
$appRoot = $PSScriptRoot
if (-not $PythonPath) {
    $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($launcher) {
        try {
            $PythonPath = & $launcher.Source -3 -c 'import sys; print(sys.executable)' 2>$null
            if ($LASTEXITCODE -ne 0) { $PythonPath = $null }
        } catch { $PythonPath = $null }
    }
    if (-not $PythonPath) {
        $python = Get-Command python.exe -ErrorAction SilentlyContinue
        if ($python) { $PythonPath = $python.Source }
    }
}
if (-not $PythonPath -or -not (Test-Path -LiteralPath $PythonPath)) {
    throw 'Python 3.11+ is required. Install Python from python.org, then run this script again.'
}
& $PythonPath -c 'import sys, tkinter, venv; assert sys.version_info >= (3,11); print(sys.version)'
if ($LASTEXITCODE -ne 0) { throw 'Python 3.11+, tkinter and venv are required.' }
if ($CheckOnly) { Write-Output 'Prerequisite check passed. No changes made.'; exit 0 }
$venvRoot = Join-Path $appRoot '.venv'
$venvPython = Join-Path $venvRoot 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) {
    & $PythonPath -m venv $venvRoot
    if ($LASTEXITCODE -ne 0) { throw 'Failed to create the local Python environment.' }
}
& $venvPython -m pip install -r (Join-Path $appRoot 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Check network/proxy settings.' }
& $venvPython -c 'import tkinter, websocket; print(websocket.__version__)'
if ($LASTEXITCODE -ne 0) { throw 'Runtime verification failed.' }
if (-not $NoShortcuts) {
    & (Join-Path $appRoot 'shortcut.ps1') -PythonPath $venvPython
    & (Join-Path $appRoot 'shortcut.ps1') -Desktop -PythonPath $venvPython
}
Write-Output 'Installation complete. Connect Codex CLI and the Claude Chrome extension as described in SETUP_FOR_AI.md.'
if (-not $NoLaunch) {
    Start-Process -FilePath (Join-Path $venvRoot 'Scripts\pythonw.exe') -ArgumentList ('"' + (Join-Path $appRoot 'launch.py') + '"') -WorkingDirectory $appRoot -WindowStyle Hidden
}
