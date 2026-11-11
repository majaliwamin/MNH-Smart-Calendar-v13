"""Single, authoritative local entry point:  python backend/run.py

* Binds to 127.0.0.1:8000 by default (see app/config.py for MNH_HOST / MNH_PORT / PORT / MNH_LAN).
* Checks that the port is free BEFORE starting Uvicorn. If it is not, it explains which
  process owns it (Windows) instead of failing with WinError 10048 and a stack trace.
* Never auto-kills anything. Use scripts\\diagnose-server.ps1 -StopStale for stale copies of
  this project.
"""
import os
import socket
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

import uvicorn  # noqa: E402
from app.config import BUILD_ID, PROJECT_ROOT, server_host, server_port  # noqa: E402


def local_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("10.255.255.255", 1))
            return sock.getsockname()[0]
    except OSError:
        return "your-computer-LAN-IP"


def port_is_free(host: str, port: int) -> bool:
    """True when this process could bind host:port right now."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        if os.name == "nt":
            # On Windows SO_REUSEADDR would allow a second listener; use exclusive use instead.
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            probe.bind((host, port))
            return True
        except OSError:
            return False


def describe_owner(port: int) -> str:
    """Best-effort description of the Windows process listening on the port."""
    if os.name != "nt":
        return f"Run: lsof -i :{port}   (or: ss -ltnp | grep :{port})"
    ps = (
        f"$c = Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1;"
        "if ($c) { $p = Get-CimInstance Win32_Process -Filter \"ProcessId=$($c.OwningProcess)\";"
        "'PID {0}  parent {1}`n{2}`n{3}' -f $p.ProcessId,$p.ParentProcessId,$p.ExecutablePath,$p.CommandLine }"
    )
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=15)
        return out.stdout.strip() or "Owner could not be determined (try an Administrator PowerShell)."
    except Exception as exc:  # pragma: no cover - diagnostic only
        return f"Owner lookup failed: {exc}"


if __name__ == "__main__":
    host, port = server_host(), server_port()
    if not port_is_free(host, port):
        print(f"\nPORT {port} IS ALREADY IN USE on {host}. Nothing was started.\n", flush=True)
        print("Process currently listening:\n" + describe_owner(port) + "\n", flush=True)
        print("What to do:", flush=True)
        print("  1. If it is an older MNH Calendar server (command line mentions this or another")
        print("     copy of 'backend\\run.py' / 'app.main:app'), stop it with:")
        print("         .\\scripts\\diagnose-server.ps1 -StopStale")
        print("  2. If it is another application, leave it alone and start this one on another port:")
        print("         $env:MNH_PORT = 8001; .\\run.ps1")
        print("  3. The browser must then use the same port: http://127.0.0.1:<port>/\n", flush=True)
        sys.exit(2)
    shown = "127.0.0.1" if host in ("0.0.0.0", "127.0.0.1") else host
    print(f"MNH Smart Calendar build {BUILD_ID}", flush=True)
    print(f"  Project folder : {PROJECT_ROOT}", flush=True)
    print(f"  Listening on   : {host}:{port}  (process id {os.getpid()})", flush=True)
    print(f"  Open           : http://{shown}:{port}/", flush=True)
    print(f"  API docs       : http://{shown}:{port}/docs", flush=True)
    print(f"  Health / build : http://{shown}:{port}/health", flush=True)
    if host == "0.0.0.0":
        print(f"  Other devices on this LAN: http://{local_ip()}:{port}/", flush=True)
    print("  Stop with Ctrl+C (closing the terminal tab also stops it).", flush=True)
    # reload spawns a second process on Windows and is the usual source of orphaned listeners.
    uvicorn.run("app.main:app", app_dir=str(BACKEND_DIR), host=host, port=port,
                reload=os.getenv("MNH_RELOAD", "false").lower() == "true")
