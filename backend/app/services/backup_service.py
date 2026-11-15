"""Database snapshots with SQLite compatibility and PostgreSQL support."""
import json
import os
import sqlite3
import threading
import time
from app.config import DATABASE_PATH, BACKUP_DIR, BACKUP_INTERVAL_SECONDS, BACKUP_RETENTION, ensure_directories


def _postgres_enabled():
    return bool(os.getenv("DATABASE_URL", "").strip())


def list_backups():
    ensure_directories()
    suffix = ".json" if _postgres_enabled() else ".sqlite3"
    return sorted([BACKUP_DIR / n for n in os.listdir(BACKUP_DIR) if n.endswith(suffix)],
                  key=lambda p: p.stat().st_mtime, reverse=True)


def make_backup():
    ensure_directories()
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
    if _postgres_enabled():
        from app.database.connection import database
        target = BACKUP_DIR / f"mnh-calendar-{stamp}.json"
        snapshot = {}
        with database() as connection:
            for table, order in (("docs", "col,id"), ("audit", "seq"), ("app_meta", "key"),
                                 ("reminder_log", "ikey"), ("comm_audit", "id")):
                rows = connection.execute(f"SELECT * FROM {table} ORDER BY {order}").fetchall()
                snapshot[table] = [dict(row) for row in rows]
        target.write_text(json.dumps({"format": "mnh-postgres-snapshot-v1",
                                      "created_at": int(time.time()*1000),
                                      "tables": snapshot}, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        if not DATABASE_PATH.exists():
            from app.database.connection import connect
            c = connect(); c.close()
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
