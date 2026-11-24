<#
Install the hidden, self-healing local MNH Calendar launcher.

Run once on the Windows laptop:
  powershell -ExecutionPolicy Bypass -File .\scripts\install-local-autostart.ps1

The existing Startup shortcut is saved outside the repository, then replaced with a
hidden launcher. The launcher starts/restarts the backend on the installed PWA port
(8017 by default) and opens the saved app window only after /health passes.

Remove it later with:
  powershell -ExecutionPolicy Bypass -File .\scripts\install-local-autostart.ps1 -Uninstall
#>
param(
    [int]$Port = $(if ($env:MNH_PORT) { [int]$env:MNH_PORT } elseif ($env:PORT) { [int]$env:PORT } else { 8017 }),
    [switch]$Uninstall
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$StartupDir = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Startup'
$ShortcutPath = Join-Path $StartupDir 'MNH Calendar.lnk'
$ConfigDir = Join-Path $env:LOCALAPPDATA 'MNH Calendar'
$ConfigPath = Join-Path $ConfigDir 'startup-config.json'
$Launcher = Join-Path $ProjectRoot 'scripts\local-autostart.ps1'
$PowerShellExe = Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
$LaunchArguments = '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}" -LaunchApp' -f $Launcher
$Shell = New-Object -ComObject WScript.Shell

if (-not (Test-Path $Launcher)) { throw "Missing launcher: $Launcher" }
New-Item -ItemType Directory -Force -Path $StartupDir | Out-Null
New-Item -ItemType Directory -Force -Path $ConfigDir | Out-Null

if ($Uninstall) {
    if (Test-Path (Join-Path $ProjectRoot 'logs\local-autostart.lock')) {
        $watcherPid = 0
        if ([int]::TryParse((Get-Content -LiteralPath (Join-Path $ProjectRoot 'logs\local-autostart.lock') -Raw).Trim(), [ref]$watcherPid)) {
            $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$watcherPid" -ErrorAction SilentlyContinue
            if ($proc -and $proc.CommandLine -like '*local-autostart.ps1*') {
                Stop-Process -Id $watcherPid -Force -ErrorAction SilentlyContinue
                Write-Host "Stopped hidden watcher (PID $watcherPid)."
            }
        }
    }

    if (Test-Path $ConfigPath) {
        $saved = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
        $restore = $Shell.CreateShortcut($ShortcutPath)
        $restore.TargetPath = $saved.TargetPath
        $restore.Arguments = $saved.Arguments
        $restore.WorkingDirectory = $saved.WorkingDirectory
        $restore.IconLocation = $saved.IconLocation
        $restore.Description = $saved.Description
        $restore.Save()
        Write-Host "Restored the original Startup shortcut."
    } elseif (Test-Path $ShortcutPath) {
        Remove-Item -LiteralPath $ShortcutPath -Force
        Write-Host "Removed the MNH Calendar Startup shortcut."
    }

    Write-Host "Autostart removed. The backend can still be started manually with .\run.ps1."
    exit 0
}

$existingSaved = $null
if (Test-Path $ConfigPath) {
    try { $existingSaved = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json } catch { }
}

if (Test-Path $ShortcutPath) {
    $current = $Shell.CreateShortcut($ShortcutPath)
    $isOurLauncher = ($current.TargetPath -eq $PowerShellExe -and $current.Arguments -like '*local-autostart.ps1*')
    if ($isOurLauncher -and $existingSaved) {
        # Re-running the installer must not overwrite the saved PWA with itself.
        $saved = $existingSaved
    } else {
        $saved = [ordered]@{
            TargetPath       = $current.TargetPath
            Arguments        = $current.Arguments
            WorkingDirectory = $current.WorkingDirectory
            IconLocation     = $current.IconLocation
            Description      = $current.Description
        }
    }
} else {
    $edge = 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
    if (-not (Test-Path $edge)) { $edge = 'msedge.exe' }
    $saved = [ordered]@{
        TargetPath      = $edge
        Arguments       = "--app=http://127.0.0.1:$Port/"
        WorkingDirectory = $ProjectRoot
        IconLocation    = ''
        Description     = 'Maternal and Neonatal Health academic timetable and calendar.'
    }
}

$saved | ConvertTo-Json | Set-Content -LiteralPath $ConfigPath -Encoding UTF8

$shortcut = $Shell.CreateShortcut($ShortcutPath)
$shortcut.TargetPath = $PowerShellExe
$shortcut.Arguments = $LaunchArguments
$shortcut.WorkingDirectory = $ProjectRoot
$shortcut.IconLocation = $saved.IconLocation
$shortcut.Description = 'Starts and keeps the local MNH Calendar backend running.'
$shortcut.Save()

Write-Host "Installed hidden MNH Calendar autostart on port $Port."
Write-Host "Startup shortcut: $ShortcutPath"
Write-Host "Saved app window: $($saved.TargetPath) $($saved.Arguments)"
Write-Host "Starting it now..."

Start-Process -FilePath $PowerShellExe -ArgumentList $LaunchArguments -WindowStyle Hidden

for ($i = 0; $i -lt 60; $i++) {
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 3 -ErrorAction Stop
        if ($health.ok -eq $true) {
            Write-Host "Ready: http://127.0.0.1:$Port/ (build $($health.build))"
            Write-Host "Logs: $ProjectRoot\logs\local-autostart.log"
            exit 0
        }
    } catch { }
    Start-Sleep -Seconds 1
}

Write-Warning "The launcher was installed, but /health did not answer within 60 seconds. Check logs\local-autostart.log and logs\local-server.err.log."
