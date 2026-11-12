
"""SQLite snapshots and PostgreSQL-aware backup handling."""
import os
import sqlite3
import threading
import time

from app.config import (
    DATABASE_PATH,
    BACKUP_DIR,
    BACKUP_INTERVAL_SECONDS,
    BACKUP_RETENTION,
    ensure_directories,
)


def _using_postgres():
    return bool(os.environ.get("DATABASE_URL", "").strip())


def list_backups():
    """List local SQLite snapshots; PostgreSQL uses persistent Neon storage."""
    if _using_postgres():
        return []

    ensure_directories()

    return sorted(
        [
            BACKUP_DIR / name
            for name in os.listdir(BACKUP_DIR)
            if name.endswith(".sqlite3")
        ],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def make_backup():
    """Create a local SQLite snapshot when SQLite is the active database."""
    if _using_postgres():
        return None

    ensure_directories()

    if not DATABASE_PATH.exists():
        from app.database.connection import connect

        connection = connect()
        connection.close()

    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
    target = BACKUP_DIR / f"mnh-calendar-{stamp}.sqlite3"

    source = sqlite3.connect(str(DATABASE_PATH), timeout=30)
    destination = sqlite3.connect(str(target))

    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()

    for old in list_backups()[BACKUP_RETENTION:]:
        try:
            old.unlink()
        except OSError:
            pass

    return target


def backup_worker(stop_event: threading.Event):
    """Run periodic local snapshots only when SQLite is active."""
    if _using_postgres():
        return

    while not stop_event.is_set():
        try:
            backups = list_backups()
            newest = backups[0].stat().st_mtime if backups else 0

            if time.time() - newest >= BACKUP_INTERVAL_SECONDS:
                make_backup()

        except Exception as exc:
            print(f"Automatic backup warning: {exc}", flush=True)

        stop_event.wait(min(3600, BACKUP_INTERVAL_SECONDS))
