"""Consistent SQLite snapshots and retention."""
import os
import sqlite3
import threading
import time
from app.config import DATABASE_PATH, BACKUP_DIR, BACKUP_INTERVAL_SECONDS, BACKUP_RETENTION, ensure_directories


def list_backups():
    ensure_directories()
    return sorted([BACKUP_DIR / n for n in os.listdir(BACKUP_DIR) if n.endswith(".sqlite3")],
                  key=lambda p: p.stat().st_mtime, reverse=True)


def make_backup():
    ensure_directories()
    if not DATABASE_PATH.exists():
        from app.database.connection import connect
        c = connect(); c.close()
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
    target = BACKUP_DIR / f"mnh-calendar-{stamp}.sqlite3"
    source = sqlite3.connect(str(DATABASE_PATH), timeout=30)
    destination = sqlite3.connect(str(target))
    try:
        source.backup(destination)
    finally:
        destination.close(); source.close()
    for old in list_backups()[BACKUP_RETENTION:]:
        try: old.unlink()
        except OSError: pass
    return target


def backup_worker(stop_event: threading.Event):
    while not stop_event.is_set():
        try:
            backups = list_backups()
            newest = backups[0].stat().st_mtime if backups else 0
            if time.time() - newest >= BACKUP_INTERVAL_SECONDS:
                make_backup()
        except Exception as exc:
            print(f"Automatic backup warning: {exc}", flush=True)
        stop_event.wait(min(3600, BACKUP_INTERVAL_SECONDS))
