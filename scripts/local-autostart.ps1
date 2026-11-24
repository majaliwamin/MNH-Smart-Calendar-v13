<#
Self-healing local launcher for the installed MNH Calendar PWA.

Started hidden from the Windows Startup shortcut. It:
  1. reuses (or creates) the project .venv,
  2. installs backend requirements only when missing,
  3. starts the existing backend entry point on the PWA port (default 8017),
  4. waits for /health before opening the saved Edge app shortcut,
  5. keeps watching and restarts the server if it crashes.

It never kills an unidentified process holding the port.
#>
param(
    [int]$Port = $(if ($env:MNH_PORT) { [int]$env:MNH_PORT } elseif ($env:PORT) { [int]$env:PORT } else { 8017 }),
    [switch]$LaunchApp,
    [switch]$NoWatch
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

$LogDir = Join-Path $ProjectRoot 'logs'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogFile = Join-Path $LogDir 'local-autostart.log'
$ServerOut = Join-Path $LogDir 'local-server.out.log'
$ServerErr = Join-Path $LogDir 'local-server.err.log'
$LockFile = Join-Path $LogDir 'local-autostart.lock'

function Write-Log {
    param([string]$Message)
    $line = '[{0}] {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Message
    Add-Content -LiteralPath $LogFile -Value $line -Encoding UTF8
    try {
        $lines = @(Get-Content -LiteralPath $LogFile -ErrorAction SilentlyContinue)
        if ($lines.Count -gt 2000) { $lines | Select-Object -Last 1000 | Set-Content -LiteralPath $LogFile -Encoding UTF8 }
    } catch { }
}

function Test-IsThisWatcher {
    param([int]$ProcessId)
    try {
        $p = Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId" -ErrorAction Stop
        return ($p.CommandLine -like '*local-autostart.ps1*')
    } catch { return $false }
}

if (Test-Path $LockFile) {
    $oldPid = 0
    if ([int]::TryParse((Get-Content -LiteralPath $LockFile -Raw).Trim(), [ref]$oldPid)) {
        if ((Get-Process -Id $oldPid -ErrorAction SilentlyContinue) -and (Test-IsThisWatcher -ProcessId $oldPid)) {
            Write-Log "Another MNH autostart watcher is already running (PID $oldPid). Exiting."
            exit 0
        }
    }
}
Set-Content -LiteralPath $LockFile -Value $PID -Encoding UTF8

function Get-VenvPython {
    $venvDir = Join-Path $ProjectRoot '.venv'
    $venvPython = Join-Path $venvDir 'Scripts\python.exe'
    if (-not (Test-Path $venvPython)) {
        Write-Log 'Creating the local Python environment.'
        if (Get-Command py -ErrorAction SilentlyContinue) { & py -3 -m venv $venvDir } else { & python -m venv $venvDir }
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path $venvPython)) { throw 'Could not create the Python virtual environment.' }
    }
    & $venvPython -c 'import fastapi, uvicorn' *> $null
    if ($LASTEXITCODE -ne 0) {
        Write-Log 'Installing missing backend requirements.'
        & $venvPython -m pip install --disable-pip-version-check -r (Join-Path $ProjectRoot 'backend\requirements.txt')
        if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed.' }
    }
    return $venvPython
}

function Test-Health {
    try {
        $response = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 3 -ErrorAction Stop
        return ($response.ok -eq $true -and [bool]$response.build)
    } catch { return $false }
}

function Get-PortOwner {
    $connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $connection) { return $null }
    return (Get-CimInstance Win32_Process -Filter "ProcessId=$($connection.OwningProcess)" -ErrorAction SilentlyContinue)
}

$script:serverProcess = $null

function Start-MnhServer {
    param([string]$PythonExe)

    if (Test-Health) { Write-Log "Server already healthy on port $Port."; return $null }

    $owner = Get-PortOwner
    if ($owner) {
        $recognised = $owner.CommandLine -match 'backend[\\/]run\.py|app\.main:app'
        Write-Log ("Port {0} is held by PID {1} ({2}). {3}" -f $Port, $owner.ProcessId, $owner.ExecutablePath, $(if ($recognised) { 'Waiting for it to become healthy.' } else { 'Leaving it alone.' }))
        return $null
    }

    Write-Log "Starting MNH Calendar backend on 127.0.0.1:$Port."
    $env:MNH_HOST = '127.0.0.1'
    $env:MNH_PORT = "$Port"
    $env:PORT = "$Port"
    # The project path contains spaces; quote the script argument so Python
    # receives one path instead of splitting at "Default Project".
    $runScript = Join-Path $ProjectRoot 'backend\run.py'
    $pythonArgs = '"{0}"' -f $runScript
    $script:serverProcess = Start-Process -FilePath $PythonExe -ArgumentList $pythonArgs -WorkingDirectory $ProjectRoot -PassThru -WindowStyle Hidden -RedirectStandardOutput $ServerOut -RedirectStandardError $ServerErr

    for ($i = 0; $i -lt 60; $i++) {
        if (Test-Health) { Write-Log "Health check passed on port $Port."; return $script:serverProcess }
        $script:serverProcess.Refresh()
        if ($script:serverProcess.HasExited) {
            $detail = ''
            if (Test-Path $ServerErr) { $detail = (Get-Content -LiteralPath $ServerErr -Tail 12 -ErrorAction SilentlyContinue) -join ' | ' }
            Write-Log "Backend exited early (code $($script:serverProcess.ExitCode)). $detail"
            return $null
        }
        Start-Sleep -Seconds 1
    }

    Write-Log "Backend did not become healthy within 60 seconds on port $Port."
    return $script:serverProcess
}

function Open-LocalApp {
    $configPath = Join-Path $env:LOCALAPPDATA 'MNH Calendar\startup-config.json'
    if (Test-Path $configPath) {
        try {
            $config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
            if ($config.TargetPath -and $config.Arguments) {
                Write-Log "Opening saved MNH Calendar app window."
                Start-Process -FilePath $config.TargetPath -ArgumentList $config.Arguments -WorkingDirectory $config.WorkingDirectory
                return
            }
        } catch { Write-Log "Saved app configuration could not be read: $($_.Exception.Message)" }
    }

    $edge = 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
    if (-not (Test-Path $edge)) { $edge = 'msedge.exe' }
    Write-Log "Opening MNH Calendar app window on port $Port."
    Start-Process -FilePath $edge -ArgumentList @("--app=http://127.0.0.1:$Port/")
}

try {
    Write-Log "Local autostart began for port $Port."
    $pythonExe = Get-VenvPython
    $script:serverProcess = Start-MnhServer -PythonExe $pythonExe

    if ($LaunchApp -and (Test-Health)) { Open-LocalApp }

    if ($NoWatch) { exit 0 }

    $failures = 0
    while ($true) {
        Start-Sleep -Seconds 15
        if (Test-Health) { $failures = 0; continue }

        $failures++
        Write-Log "Health check failed ($failures/3)."
        if ($failures -lt 3) { continue }

        if ($script:serverProcess -and -not $script:serverProcess.HasExited) {
            Write-Log "Stopping unresponsive backend process $($script:serverProcess.Id)."
            Stop-Process -Id $script:serverProcess.Id -Force -ErrorAction SilentlyContinue
        }
        $script:serverProcess = Start-MnhServer -PythonExe $pythonExe
        $failures = 0
    }
} catch {
    Write-Log "FATAL: $($_.Exception.Message)"
    exit 1
} finally {
    Remove-Item -LiteralPath $LockFile -Force -ErrorAction SilentlyContinue
}
