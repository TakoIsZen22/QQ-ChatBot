$ErrorActionPreference='Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if (Get-NetTCPConnection -State Listen -LocalAddress 127.0.0.1 -LocalPort 3001 -ErrorAction SilentlyContinue) {
    Write-Output 'NapCat OneBot is already running.'
    exit 0
}
& "$projectRoot\.venv\Scripts\python.exe" "$projectRoot\tools\harden-napcat.py"
if ($LASTEXITCODE -ne 0) {exit $LASTEXITCODE}
Start-Process -FilePath "$projectRoot\.venv\Scripts\python.exe" -ArgumentList ('"' + "$projectRoot\tools\launch-napcat.py" + '"') -WorkingDirectory $projectRoot -WindowStyle Hidden
Write-Output 'NapCat started in background. First-time QR login still requires tools\start-napcat.bat.'
