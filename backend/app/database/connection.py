
"""SQLite and PostgreSQL database connection helpers."""
import json
import os
import sqlite3
import time
from contextlib import contextmanager
from threading import RLock

from app.config import DATABASE_PATH, ensure_directories

DB_LOCK = RLock()


def is_postgres():
    return bool(os.environ.get("DATABASE_URL", "").strip())


SEED_MODULES = {
    "MIPN 8100": {
        "title": "Medical Imaging in Pregnancy and Neonates",
        "facilitator": "Not specified",
    },
    "ARMN – 8100": {
        "title": "Antimicrobial Resistance in Maternal & Neonatal Health",
        "facilitator": "G Bandawe",
    },
    "PNIM-8100": {
        "title": "Pregnancy and Neonatal Immunology",
        "facilitator": "D Mzinza",
    },
}

SEED_PROGRAM_CELLS = {
    "1_0": {"code": "Biostatistics", "title": "Biostatistics", "timeLabel": "11:00–13:30", "colour": "#2F5D8C"},
    "6_0": {"code": "Bioethics", "title": "Bioethics", "timeLabel": "19:00–21:00", "colour": "#7B3F61"},
    "6_1": {"code": "Bioethics", "title": "Bioethics", "timeLabel": "19:00–21:00", "colour": "#7B3F61"},
    "0_2": {"code": "Immunology", "title": "Immunology", "timeLabel": "08:00–10:00", "colour": "#3C7A5A"},
    "3_2": {"code": "Imaging", "title": "Imaging", "timeLabel": "Afternoon–evening", "colour": "#8A6D2F"},
    "1_3": {"code": "Seminar in MNH", "title": "Seminar in Maternal and Neonatal Health", "timeLabel": "10:00–12:00", "colour": "#2F5D8C"},
    "2_3": {"code": "Biostatistics", "title": "Biostatistics", "timeLabel": "AM–afternoon", "colour": "#2F5D8C"},
    "6_3": {"code": "Immunology", "title": "Immunology", "timeLabel": "19:00–21:00", "colour": "#3C7A5A"},
    "0_4": {"code": "Immunology", "title": "Immunology", "timeLabel": "08:00–10:00", "colour": "#3C7A5A"},
    "3_4": {"code": "Library", "title": "Library session", "timeLabel": "Afternoon", "colour": "#4B5D7A"},
}


def _convert_placeholders(sql):
    """Convert ? placeholders to %s without changing quoted text."""
    result = []
    state = "normal"
    i = 0

    while i < len(sql):
        char = sql[i]
        next_char = sql[i + 1] if i + 1 < len(sql) else ""

        if state == "normal":
            if char == "'":
                state = "single"
                result.append(char)
            elif char == '"':
                state = "double"
                result.append(char)
            elif char == "-" and next_char == "-":
                state = "line_comment"
                result.extend([char, next_char])
                i += 1
            elif char == "/" and next_char == "*":
                state = "block_comment"
                result.extend([char, next_char])
                i += 1
            elif char == "?":
                result.append("%s")
            else:
                result.append(char)

        elif state == "single":
            result.append(char)
            if char == "'" and next_char == "'":
                result.append(next_char)
                i += 1
            elif char == "'":
                state = "normal"

        elif state == "double":
            result.append(char)
            if char == '"' and next_char == '"':
                result.append(next_char)
                i += 1
            elif char == '"':
                state = "normal"

        elif state == "line_comment":
            result.append(char)
            if char == "\n":
                state = "normal"

        elif state == "block_comment":
            result.append(char)
            if char == "*" and next_char == "/":
                result.append(next_char)
                i += 1
                state = "normal"

        i += 1

    return "".join(result)


class HybridRow(dict):
    """Support both row['column'] and row[0] access."""

    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class PostgresCursor:
    def __init__(self, cursor):
        self.cursor = cursor

    def fetchone(self):
        row = self.cursor.fetchone()
        if row is None:
            return None
        names = [column.name for column in self.cursor.description]
        return HybridRow(zip(names, row))

    def fetchall(self):
        rows = self.cursor.fetchall()
        names = [column.name for column in self.cursor.description]
        return [HybridRow(zip(names, row)) for row in rows]

    @property
    def rowcount(self):
        return self.cursor.rowcount

    @property
    def description(self):
        return self.cursor.description

    def close(self):
        self.cursor.close()


class PostgresConnection:
    """Compatibility wrapper for the application's SQLite-style calls."""

    def __init__(self, connection):
        self.connection = connection

    def execute(self, sql, parameters=()):
        cursor = self.connection.cursor()
        cursor.execute(_convert_placeholders(sql), parameters)
        return PostgresCursor(cursor)

    def executemany(self, sql, parameters):
        cursor = self.connection.cursor()
        cursor.executemany(_convert_placeholders(sql), parameters)
        return PostgresCursor(cursor)

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()

    def close(self):
        self.connection.close()


def _insert_doc(connection, collection, item_id, data, updated_at):
    sql = """
        INSERT INTO docs(col,id,data,updated_at)
        VALUES(?,?,?,?)
    """
    if is_postgres():
        sql += " ON CONFLICT(col,id) DO NOTHING"
    else:
        sql = sql.replace("INSERT INTO", "INSERT OR IGNORE INTO", 1)

    connection.execute(sql, (collection, item_id, data, updated_at))


def _insert_meta(connection, key, value):
    sql = "INSERT INTO app_meta(key,value) VALUES(?,?)"
    if is_postgres():
        sql += " ON CONFLICT(key) DO NOTHING"
    else:
        sql = sql.replace("INSERT INTO", "INSERT OR IGNORE INTO", 1)

    connection.execute(sql, (key, value))


def _replace_meta(connection, key, value):
    if is_postgres():
        sql = """
            INSERT INTO app_meta(key,value) VALUES(?,?)
            ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value
        """
    else:
        sql = "INSERT OR REPLACE INTO app_meta(key,value) VALUES(?,?)"

    connection.execute(sql, (key, value))


def _connect_sqlite():
    ensure_directories()

    connection = sqlite3.connect(
        str(DATABASE_PATH),
        timeout=30,
        check_same_thread=False,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=30000")

    connection.execute("""
        CREATE TABLE IF NOT EXISTS docs(
            col TEXT NOT NULL,
            id TEXT NOT NULL,
            data TEXT NOT NULL,
            updated_at INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(col,id)
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS audit(
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            at INTEGER NOT NULL,
            role TEXT NOT NULL,
            action TEXT NOT NULL,
            collection TEXT,
            item_id TEXT,
            summary TEXT NOT NULL
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS app_meta(
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    return connection


def _connect_postgres():
    try:
        import psycopg
        from psycopg.rows import tuple_row
    except ImportError as exc:
        raise RuntimeError(
            "PostgreSQL driver is missing. Install backend requirements."
        ) from exc

    raw_connection = psycopg.connect(
        os.environ["DATABASE_URL"],
        connect_timeout=15,
        row_factory=tuple_row,
    )

    connection = PostgresConnection(raw_connection)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS docs(
            col TEXT NOT NULL,
            id TEXT NOT NULL,
            data TEXT NOT NULL,
            updated_at BIGINT NOT NULL DEFAULT 0,
            PRIMARY KEY(col,id)
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS audit(
            seq BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            at BIGINT NOT NULL,
            role TEXT NOT NULL,
            action TEXT NOT NULL,
            collection TEXT,
            item_id TEXT,
            summary TEXT NOT NULL
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS app_meta(
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    return connection


def _seed_database(connection):
    count = connection.execute(
        "SELECT COUNT(*) FROM docs WHERE col='modules'"
    ).fetchone()[0]

    if count == 0:
        now = int(time.time() * 1000)
        for code, data in SEED_MODULES.items():
            _insert_doc(
                connection,
                "modules",
                code,
                json.dumps(data, ensure_ascii=False),
                now,
            )

    seeded = connection.execute(
        "SELECT 1 FROM app_meta WHERE key='academic_activity_seed_v1'"
    ).fetchone()

    if not seeded:
        now = int(time.time() * 1000)

        _insert_doc(
            connection,
            "examinations",
            "exam-2026-11-13",
            json.dumps({
                "title": "Examination",
                "date": "2026-11-13",
                "time": "",
                "venue": "",
                "notes": "Time and venue have not been specified.",
            }, ensure_ascii=False),
            now,
        )

        _insert_doc(
            connection,
            "recurring",
            "journal-club",
            json.dumps({
                "title": "Journal Club",
                "frequency": "Weekly",
                "day": "Tuesday",
                "time": "13:00–14:00",
                "notes": "Recurring academic discussion.",
            }, ensure_ascii=False),
            now,
        )

        _insert_meta(connection, "academic_activity_seed_v1", "1")

    # Preserve records outside Monday-Friday for administrator review.
    flagged = []

    for row in connection.execute(
        "SELECT id,data FROM docs WHERE col='cells'"
    ).fetchall():
        item_id = str(row["id"])
        legacy = item_id.rsplit("_", 1)
        day_index = None

        is_legacy_cell = (
            len(legacy) == 2
            and legacy[1].isdigit()
            and legacy[0].isdigit()
        )

        if is_legacy_cell:
            day_index = int(legacy[1])

        try:
            record = json.loads(row["data"])
        except (TypeError, json.JSONDecodeError):
            record = {}

        if not is_legacy_cell:
            raw_day = record.get("dayIndex")
            if type(raw_day) is int:
                day_index = raw_day
            elif isinstance(raw_day, str) and raw_day.isdigit():
                day_index = int(raw_day)

        if day_index is not None and day_index >= 5:
            flagged.append({
                "collection": "cells",
                "id": item_id,
                "reason": (
                    f"weekday index {day_index} is outside Monday–Friday"
                ),
            })

    for row in connection.execute(
        "SELECT id,data FROM docs WHERE col='recurring'"
    ).fetchall():
        try:
            recurring_data = json.loads(row["data"])
        except (TypeError, json.JSONDecodeError):
            recurring_data = {}

        if str(recurring_data.get("day", "")).strip().lower() in (
            "sat",
            "saturday",
        ):
            flagged.append({
                "collection": "recurring",
                "id": str(row["id"]),
                "reason": "scheduled on Saturday",
            })

    previous = connection.execute(
        "SELECT value FROM app_meta "
        "WHERE key='flagged_non_weekday_records'"
    ).fetchone()

    flagged_json = json.dumps(
        flagged,
        ensure_ascii=False,
        sort_keys=True,
    )

    if flagged and (
        not previous or previous["value"] != flagged_json
    ):
        _replace_meta(
            connection,
            "flagged_non_weekday_records",
            flagged_json,
        )

        connection.execute(
            """
            INSERT INTO audit(
                at,role,action,collection,item_id,summary
            )
            VALUES(?,?,?,?,?,?)
            """,
            (
                int(time.time() * 1000),
                "system",
                "flagged",
                None,
                None,
                f"{len(flagged)} record(s) fall outside Monday–Friday "
                "and are hidden from the timetable; "
                "they were kept for review.",
            ),
        )

    elif not flagged and previous:
        connection.execute(
            "DELETE FROM app_meta "
            "WHERE key='flagged_non_weekday_records'"
        )

    program_seeded = connection.execute(
        "SELECT 1 FROM app_meta WHERE key='weekly_program_seed_v1'"
    ).fetchone()

    if not program_seeded:
        now = int(time.time() * 1000)

        for cell_id, data in SEED_PROGRAM_CELLS.items():
            _insert_doc(
                connection,
                "cells",
                cell_id,
                json.dumps(data, ensure_ascii=False),
                now,
            )

        _insert_meta(connection, "weekly_program_seed_v1", "1")


def connect():
    """Connect to the configured database and initialise its schema."""
    connection = (
        _connect_postgres() if is_postgres() else _connect_sqlite()
    )

    try:
        _seed_database(connection)
        connection.commit()
        return connection
    except Exception:
        connection.rollback()
        connection.close()
        raise


@contextmanager
def database():
    """Provide a committed or rolled-back transaction."""
    if is_postgres():
        connection = connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
    else:
        with DB_LOCK:
            connection = connect()
            try:
                yield connection
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()
