"""PostgreSQL persistence and one-time SQLite migration for Neon."""
from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
import time
from pathlib import Path

import psycopg
from psycopg.rows import tuple_row

_READY = False
_READY_LOCK = threading.Lock()
_PRIMARY_KEYS = {"docs": ("col", "id"), "app_meta": ("key",), "reminder_log": ("ikey",)}
_SEED_MODULES = {
    "MIPN 8100": {"title": "Medical Imaging in Pregnancy and Neonates", "facilitator": "Not specified"},
    "ARMN – 8100": {"title": "Antimicrobial Resistance in Maternal & Neonatal Health", "facilitator": "G Bandawe"},
    "PNIM-8100": {"title": "Pregnancy and Neonatal Immunology", "facilitator": "D Mzinza"},
}


class HybridRow(dict):
    """Mapping row that also supports SQLite-style integer indexing."""
    def __init__(self, columns, values):
        super().__init__(zip(columns, values))
        self._values = tuple(values)

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return super().__getitem__(key)


def _row_factory(cursor):
    columns = [item.name for item in cursor.description]
    return lambda values: HybridRow(columns, values)


def adapt_sql(sql: str) -> str:
    """Translate the small SQLite SQL compatibility surface used by this app."""
    sql = sql.replace("?", "%s")
    sql = re.sub(r"INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT", "BIGSERIAL PRIMARY KEY", sql, flags=re.I)
    match = re.match(
        r"\s*INSERT\s+OR\s+(REPLACE|IGNORE)\s+INTO\s+(\w+)\s*\(([^)]+)\)(\s*VALUES\s*\(.*)",
        sql, flags=re.I | re.S,
    )
    if not match:
        return sql
    mode, table, columns, tail = match.groups()
    column_names = [part.strip().strip('"') for part in columns.split(",")]
    prefix = f"INSERT INTO {table} ({columns}){tail}"
    if mode.upper() == "IGNORE":
        return prefix + " ON CONFLICT DO NOTHING"
    keys = _PRIMARY_KEYS.get(table.lower())
    if not keys:
        raise RuntimeError(f"PostgreSQL compatibility: no conflict key configured for {table}")
    updates = [name for name in column_names if name not in keys]
    if not updates:
        return prefix + " ON CONFLICT DO NOTHING"
    assignments = ", ".join(f"{name}=EXCLUDED.{name}" for name in updates)
    return prefix + f" ON CONFLICT ({', '.join(keys)}) DO UPDATE SET {assignments}"


class Connection:
    def __init__(self, raw):
        self.raw = raw

    def execute(self, sql, params=None):
        return self.raw.execute(adapt_sql(sql), params or ())

    def executemany(self, sql, params):
        return self.raw.executemany(adapt_sql(sql), params)

    def commit(self):
        self.raw.commit()

    def rollback(self):
        self.raw.rollback()

    def close(self):
        self.raw.close()


def _raw_connect():
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL is required for PostgreSQL storage.")
    return psycopg.connect(url, row_factory=_row_factory, connect_timeout=15)


def _copy_sqlite_table(source, target, table, columns, conflict_sql):
    exists = source.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    if not exists:
        return 0
    rows = source.execute(f"SELECT {', '.join(columns)} FROM {table}").fetchall()
    if not rows:
        return 0
    placeholders = ", ".join(["%s"] * len(columns))
    statement = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders}) {conflict_sql}"
    with target.cursor() as cursor:
        cursor.executemany(statement, [tuple(row) for row in rows])
    return len(rows)


def _initialise():
    global _READY
    with _READY_LOCK:
        if _READY:
            return
        raw = _raw_connect()
        try:
            raw.execute("""CREATE TABLE IF NOT EXISTS docs(
                col TEXT NOT NULL, id TEXT NOT NULL, data TEXT NOT NULL,
                updated_at BIGINT NOT NULL DEFAULT 0, PRIMARY KEY(col,id))""")
            raw.execute("""CREATE TABLE IF NOT EXISTS audit(
                seq BIGSERIAL PRIMARY KEY, at BIGINT NOT NULL, role TEXT NOT NULL,
                action TEXT NOT NULL, collection TEXT, item_id TEXT, summary TEXT NOT NULL)""")
            raw.execute("CREATE TABLE IF NOT EXISTS app_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            raw.execute("""CREATE TABLE IF NOT EXISTS reminder_log(
                ikey TEXT PRIMARY KEY, sent_at TEXT NOT NULL, phone TEXT, code TEXT,
                starts TEXT, lead INTEGER, status TEXT, detail TEXT)""")
            raw.execute("""CREATE TABLE IF NOT EXISTS comm_audit(
                id BIGSERIAL PRIMARY KEY, at TEXT NOT NULL, actor TEXT,
                action TEXT NOT NULL, target TEXT, detail TEXT)""")

            marker = raw.execute("SELECT value FROM app_meta WHERE key='sqlite_migration_v1'").fetchone()
            if not marker:
                from app.config import DATABASE_PATH
                db_path = Path(DATABASE_PATH)
                migrated = 0
                if db_path.is_file():
                    source = sqlite3.connect(str(db_path))
                    try:
                        migrated += _copy_sqlite_table(source, raw, "docs",
                            ["col", "id", "data", "updated_at"], "ON CONFLICT (col,id) DO NOTHING")
                        migrated += _copy_sqlite_table(source, raw, "audit",
                            ["seq", "at", "role", "action", "collection", "item_id", "summary"],
                            "ON CONFLICT (seq) DO NOTHING")
                        migrated += _copy_sqlite_table(source, raw, "app_meta",
                            ["key", "value"], "ON CONFLICT (key) DO NOTHING")
                        migrated += _copy_sqlite_table(source, raw, "reminder_log",
                            ["ikey", "sent_at", "phone", "code", "starts", "lead", "status", "detail"],
                            "ON CONFLICT (ikey) DO NOTHING")
                        migrated += _copy_sqlite_table(source, raw, "comm_audit",
                            ["id", "at", "actor", "action", "target", "detail"],
                            "ON CONFLICT (id) DO NOTHING")
                    finally:
                        source.close()
                raw.execute(
                    "INSERT INTO app_meta(key,value) VALUES('sqlite_migration_v1',%s) ON CONFLICT(key) DO NOTHING",
                    (json.dumps({"completed_at": int(time.time()*1000), "rows_copied": migrated,
                                 "source_found": Path(DATABASE_PATH).is_file()}),),
                )

            count = raw.execute("SELECT COUNT(*) AS count FROM docs").fetchone()["count"]
            seeded = raw.execute("SELECT 1 FROM app_meta WHERE key='postgres_initial_seed_v1'").fetchone()
            if count == 0 and not seeded:
                now = int(time.time() * 1000)
                for code, data in _SEED_MODULES.items():
                    raw.execute("INSERT INTO docs(col,id,data,updated_at) VALUES('modules',%s,%s,%s) ON CONFLICT(col,id) DO NOTHING",
                                (code, json.dumps(data, ensure_ascii=False), now))
                raw.execute("INSERT INTO docs(col,id,data,updated_at) VALUES('examinations','exam-2026-11-13',%s,%s) ON CONFLICT(col,id) DO NOTHING",
                            (json.dumps({"title":"Examination","date":"2026-11-13","time":"","venue":"",
                                         "notes":"Time and venue have not been specified."}, ensure_ascii=False), now))
                recurring = {
                    "journal-club": {"title":"Journal Club","frequency":"Weekly","day":"Tuesday","time":"13:00–14:00","notes":""},
                    "seminar-mnh": {"title":"Seminar in MNH","frequency":"Weekly","day":"Thursday","time":"10:00–12:00","notes":""},
                }
                for item_id, data in recurring.items():
                    raw.execute("INSERT INTO docs(col,id,data,updated_at) VALUES('recurring',%s,%s,%s) ON CONFLICT(col,id) DO NOTHING",
                                (item_id, json.dumps(data, ensure_ascii=False), now))
                raw.execute("INSERT INTO app_meta(key,value) VALUES('academic_activity_seed_v1','1') ON CONFLICT(key) DO NOTHING")
            raw.execute("INSERT INTO app_meta(key,value) VALUES('postgres_initial_seed_v1','1') ON CONFLICT(key) DO NOTHING")
            # Keep serial sequences valid after importing explicit SQLite IDs.
            raw.execute("SELECT setval(pg_get_serial_sequence('audit','seq'), GREATEST(COALESCE((SELECT MAX(seq) FROM audit),1),1), EXISTS(SELECT 1 FROM audit))")
            raw.execute("SELECT setval(pg_get_serial_sequence('comm_audit','id'), GREATEST(COALESCE((SELECT MAX(id) FROM comm_audit),1),1), EXISTS(SELECT 1 FROM comm_audit))")
            raw.commit()
            _READY = True
        except Exception:
            raw.rollback()
            raise
        finally:
            raw.close()


def connect():
    _initialise()
    return Connection(_raw_connect())
