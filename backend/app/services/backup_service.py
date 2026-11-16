"""Database snapshots with SQLite compatibility and PostgreSQL support."""
import json
import os
import sqlite3
import tempfile
import time
from pathlib import Path
from app.config import DATABASE_PATH, BACKUP_DIR, BACKUP_INTERVAL_SECONDS, BACKUP_RETENTION, ensure_directories


def _postgres_enabled():
    return bool(os.getenv("DATABASE_URL", "").strip())


def list_backups():
    ensure_directories()
    suffix = ".json" if _postgres_enabled() else ".sqlite3"
    return sorted([p for p in BACKUP_DIR.glob(f"*{suffix}") if p.is_file()],
                  key=lambda p: p.stat().st_mtime, reverse=True)


def _fsync_backup_directory() -> None:
    """Persist directory-entry changes where the platform supports directory fsync."""
    try:
        descriptor = os.open(str(BACKUP_DIR), os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError:
        # Some platforms/filesystems do not permit opening or syncing directories.
        pass


def _atomic_json_snapshot(target: Path, payload: dict) -> None:
    fd, temporary = tempfile.mkstemp(prefix=".mnh-backup-", suffix=".tmp", dir=str(BACKUP_DIR))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
        _fsync_backup_directory()
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def make_backup():
    """Create a complete, atomically published database snapshot.

    The final backup filename only becomes visible after the snapshot has been
    written successfully, so an interrupted write cannot masquerade as a valid copy.
    """
    ensure_directories()
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime()) + f"-{time.time_ns() % 1_000_000_000:09d}"
    if _postgres_enabled():
        from app.database.connection import database
        target = BACKUP_DIR / f"mnh-calendar-{stamp}.json"
        snapshot = {}
        with database() as connection:
            # All tables must come from one consistent point-in-time view, even while
            # other devices are editing the shared calendar.
            connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            for table, order in (("docs", "col,id"), ("audit", "seq"), ("app_meta", "key"),
                                 ("reminder_log", "ikey"), ("comm_audit", "id")):
                rows = connection.execute(f"SELECT * FROM {table} ORDER BY {order}").fetchall()
                snapshot[table] = [dict(row) for row in rows]
        _atomic_json_snapshot(target, {"format": "mnh-postgres-snapshot-v1",
                                       "created_at": int(time.time()*1000),
                                       "tables": snapshot})
    else:
        if not DATABASE_PATH.exists():
            from app.database.connection import connect
            connection = connect()
            connection.close()
        target = BACKUP_DIR / f"mnh-calendar-{stamp}.sqlite3"
        fd, temporary = tempfile.mkstemp(prefix=".mnh-backup-", suffix=".sqlite3.tmp", dir=str(BACKUP_DIR))
        os.close(fd)
        try:
            source = sqlite3.connect(str(DATABASE_PATH), timeout=30)
            destination = sqlite3.connect(temporary)
            try:
                source.backup(destination)
                integrity = destination.execute("PRAGMA integrity_check").fetchone()
                if not integrity or integrity[0] != "ok":
                    raise RuntimeError("SQLite backup failed its integrity check.")
                destination.commit()
            finally:
                destination.close()
                source.close()
            os.replace(temporary, target)
            _fsync_backup_directory()
        except Exception:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise
    # Retention is applied only after a new complete snapshot is safely published.
    for old in list_backups()[BACKUP_RETENTION:]:
        try:
            old.unlink()
        except OSError:
            pass
    return target


def backup_worker(stop_event):
    while not stop_event.is_set():
        try:
            backups = list_backups()
            newest = backups[0].stat().st_mtime if backups else 0
            if time.time() - newest >= BACKUP_INTERVAL_SECONDS:
                make_backup()
        except Exception as exc:
            print(f"Automatic backup warning: {exc}", flush=True)
        stop_event.wait(min(3600, BACKUP_INTERVAL_SECONDS))
