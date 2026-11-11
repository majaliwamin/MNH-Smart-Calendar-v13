<#
Diagnose (and optionally stop) whatever is listening on the MNH Calendar port.
  .\scripts\diagnose-server.ps1               # report only
  .\scripts\diagnose-server.ps1 -StopStale    # stop it ONLY if its command line is an MNH Calendar server
  .\scripts\diagnose-server.ps1 -Port 8001
Never kills an unidentified process.
#>
param([int]$Port = $(if ($env:MNH_PORT) { [int]$env:MNH_PORT } elseif ($env:PORT) { [int]$env:PORT } else { 8000 }), [switch]$StopStale)
$conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if (-not $conns) { Write-Host "Port $Port is free." -ForegroundColor Green; exit 0 }
foreach ($c in $conns | Sort-Object OwningProcess -Unique) {
    $p = Get-CimInstance Win32_Process -Filter "ProcessId=$($c.OwningProcess)"
    Write-Host "Port $Port is held by PID $($p.ProcessId) (parent $($p.ParentProcessId))" -ForegroundColor Yellow
    Write-Host "  Executable : $($p.ExecutablePath)"
    Write-Host "  Command    : $($p.CommandLine)"
    $mine = $p.CommandLine -match 'backend[\\/]run\.py|app\.main:app'
    if (-not $mine) { Write-Host "  Not recognisably an MNH Calendar server: left alone. Use another port: `$env:MNH_PORT=8001; .\run.ps1" -ForegroundColor Red; continue }
    if ($StopStale) { Stop-Process -Id $p.ProcessId -Force; Start-Sleep 1; Write-Host "  Stopped stale MNH server." -ForegroundColor Green }
    else { Write-Host "  Looks like an MNH Calendar server. Re-run with -StopStale to stop it." -ForegroundColor Cyan }
}
try { Write-Host ("Server answering says: " + (Invoke-RestMethod "http://127.0.0.1:$Port/api/build" -TimeoutSec 3 | ConvertTo-Json -Compress)) } catch { Write-Host "No /api/build response (older copy of the app, or a different program)." }
