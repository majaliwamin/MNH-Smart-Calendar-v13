"""SQLite connection and transaction helpers."""
import json
import sqlite3
import time
from contextlib import contextmanager
from threading import RLock
from app.config import DATABASE_PATH, ensure_directories

DB_LOCK = RLock()
SEED_MODULES = {
    "MIPN 8100": {"title": "Medical Imaging in Pregnancy and Neonates", "facilitator": "Not specified"},
    "ARMN – 8100": {"title": "Antimicrobial Resistance in Maternal & Neonatal Health", "facilitator": "G Bandawe"},
    "PNIM-8100": {"title": "Pregnancy and Neonatal Immunology", "facilitator": "D Mzinza"},
}
# Programme for the teaching week Monday 9 - Friday 13 November 2026.
# Keys are "slot_day": seven time slots by five days (0 = Monday ... 4 = Friday).
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


def connect():
    ensure_directories()
    connection = sqlite3.connect(str(DATABASE_PATH), timeout=30, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=30000")
    connection.execute("""CREATE TABLE IF NOT EXISTS docs(
        col TEXT NOT NULL, id TEXT NOT NULL, data TEXT NOT NULL,
        updated_at INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(col,id))""")
    connection.execute("""CREATE TABLE IF NOT EXISTS audit(
        seq INTEGER PRIMARY KEY AUTOINCREMENT, at INTEGER NOT NULL,
        role TEXT NOT NULL, action TEXT NOT NULL, collection TEXT,
        item_id TEXT, summary TEXT NOT NULL)""")
    connection.execute("CREATE TABLE IF NOT EXISTS app_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    count = connection.execute("SELECT COUNT(*) FROM docs WHERE col='modules'").fetchone()[0]
    if count == 0:
        now = int(time.time() * 1000)
        for code, data in SEED_MODULES.items():
            connection.execute("INSERT OR IGNORE INTO docs(col,id,data,updated_at) VALUES(?,?,?,?)",
                               ("modules", code, json.dumps(data, ensure_ascii=False), now))
    seeded = connection.execute("SELECT 1 FROM app_meta WHERE key='academic_activity_seed_v1'").fetchone()
    if not seeded:
        now = int(time.time() * 1000)
        connection.execute("INSERT OR IGNORE INTO docs(col,id,data,updated_at) VALUES(?,?,?,?)",
            ("examinations", "exam-2026-11-13", json.dumps({"title": "Examination", "date": "2026-11-13", "time": "", "venue": "", "notes": "Time and venue have not been specified."}, ensure_ascii=False), now))
        connection.execute("INSERT OR IGNORE INTO docs(col,id,data,updated_at) VALUES(?,?,?,?)",
            ("recurring", "journal-club", json.dumps({"title": "Journal Club", "frequency": "Weekly", "day": "Tuesday", "time": "13:00–14:00", "notes": "Recurring academic discussion."}, ensure_ascii=False), now))
        connection.execute("INSERT OR IGNORE INTO app_meta(key,value) VALUES('academic_activity_seed_v1','1')")
    # The academic calendar is Monday–Friday. Records that do not fit (day index >= 5, or a
    # Saturday recurring activity) are NEVER deleted: they stay in the database untouched,
    # every reader (web, mobile, exports, analytics) ignores them, and they are listed in
    # app_meta['flagged_non_weekday_records'] + the audit log so an administrator can review them.
    flagged = []
    for row in connection.execute("SELECT id,data FROM docs WHERE col='cells'").fetchall():
        item_id = str(row["id"])
        legacy = item_id.rsplit("_", 1)
        day_index = None
        is_legacy_cell = len(legacy) == 2 and legacy[1].isdigit() and legacy[0].isdigit()
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
            flagged.append({"collection": "cells", "id": item_id, "reason": f"weekday index {day_index} is outside Monday–Friday"})
    for row in connection.execute("SELECT id,data FROM docs WHERE col='recurring'").fetchall():
        try:
            recurring_data = json.loads(row["data"])
        except (TypeError, json.JSONDecodeError):
            recurring_data = {}
        if str(recurring_data.get("day", "")).strip().lower() in ("sat", "saturday"):
            flagged.append({"collection": "recurring", "id": str(row["id"]), "reason": "scheduled on Saturday"})
    previous = connection.execute("SELECT value FROM app_meta WHERE key='flagged_non_weekday_records'").fetchone()
    flagged_json = json.dumps(flagged, ensure_ascii=False, sort_keys=True)
    if flagged and (not previous or previous["value"] != flagged_json):
        connection.execute("INSERT OR REPLACE INTO app_meta(key,value) VALUES('flagged_non_weekday_records',?)", (flagged_json,))
        connection.execute("INSERT INTO audit(at,role,action,collection,item_id,summary) VALUES(?,?,?,?,?,?)",
                           (int(time.time() * 1000), "system", "flagged", None, None,
                            f"{len(flagged)} record(s) fall outside Monday–Friday and are hidden from the timetable; they were kept for review."))
    elif not flagged and previous:
        connection.execute("DELETE FROM app_meta WHERE key='flagged_non_weekday_records'")
    program_seeded = connection.execute("SELECT 1 FROM app_meta WHERE key='weekly_program_seed_v1'").fetchone()
    if not program_seeded:
        now = int(time.time() * 1000)
        for cell_id, data in SEED_PROGRAM_CELLS.items():
            connection.execute("INSERT OR IGNORE INTO docs(col,id,data,updated_at) VALUES(?,?,?,?)",
                               ("cells", cell_id, json.dumps(data, ensure_ascii=False), now))
        connection.execute("INSERT OR IGNORE INTO app_meta(key,value) VALUES('weekly_program_seed_v1','1')")
    connection.commit()
    return connection


@contextmanager
def database():
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
