$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$VenvPython = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $VenvPython)) {
    Write-Host 'Creating the project Python environment...'
    python -m venv (Join-Path $ProjectRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python virtual environment.' }
}

& $VenvPython -c 'import fastapi, uvicorn' *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Installing the backend requirements (first run only)...'
    & $VenvPython -m pip install -r (Join-Path $ProjectRoot 'backend\requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed.' }
}

& (Join-Path $ProjectRoot 'scripts\diagnose-server.ps1')

Write-Host ''
Write-Host 'Starting MNH Smart Calendar...'
Write-Host 'Web app: http://127.0.0.1:8000/'
Write-Host 'API docs: http://127.0.0.1:8000/docs'
Write-Host 'Health:   http://127.0.0.1:8000/health'
Write-Host 'Stop the server with Ctrl+C.'
& $VenvPython (Join-Path $ProjectRoot 'backend\run.py')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
