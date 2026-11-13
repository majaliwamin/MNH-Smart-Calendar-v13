"""Behavioural tests (they execute the code, unlike string-presence checks).

They avoid the web framework on purpose so they also run where FastAPI is not installed.
"""
import importlib.util
import io
import json
import os
import socket
import sqlite3
import sys
import tempfile
import types
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services import schedule  # noqa: E402
from app.services.excel_export import build_timetable_workbook  # noqa: E402

COLLECTIONS = {
    "modules": {
        "PNIM-8100": {"title": "Pregnancy and Neonatal Immunology", "facilitator": "D Mzinza", "facilitatorId": "fac-1"},
        "MIPN 8100": {"title": "Medical Imaging in Pregnancy and Neonates", "facilitator": "Not specified"},
    },
    "facilitators": {"fac-1": {"name": "Dr D Mzinza"}},
    "cells": {
        "0_0": {"code": "PNIM-8100", "title": "Immunology tutorial", "timeLabel": "08:00–10:00"},
        "s-custom": {"dayIndex": 2, "startTime": "14:15", "endTime": "16:05", "code": "MIPN 8100", "title": "Imaging lab"},
        "s-sat": {"dayIndex": 5, "startTime": "09:00", "endTime": "10:00", "code": "PNIM-8100", "title": "Saturday class"},
        "6_6": {"code": "Legacy", "timeLabel": "19:00–21:00"},   # legacy day index 6 -> ignored
    },
    "recurring": {"journal-club": {"title": "Journal Club", "day": "Tuesday", "time": "13:00–14:00"}},
}


def test_teaching_week_dates_are_monday_to_friday():
    assert schedule.WEEK_START == date(2026, 11, 9)
    assert schedule.WEEK_START.strftime("%A") == "Monday"
    assert date(2026, 11, 13).strftime("%A") == "Friday"
    assert schedule.WEEKDAY_NAMES == ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")


def test_initials_ignore_professional_titles():
    assert schedule.initials("Dr D Mzinza") == "DM"
    assert schedule.initials("Prof. Jane A. Banda") == "JB"
    assert schedule.initials("G Bandawe") == "GB"
    assert schedule.initials("Dr D. Mzinza") != "DD"


def test_saturday_and_out_of_range_cells_are_never_resolved():
    sessions = schedule.sessions_from_collections(COLLECTIONS)
    assert {s["weekday"] for s in sessions} <= set(schedule.WEEKDAY_NAMES)
    assert "Saturday class" not in {s["activity"] for s in sessions}
    assert schedule.cell_interval("x", {"dayIndex": 5, "startTime": "09:00", "endTime": "10:00"}) is None
    assert schedule.cell_interval("6_6", {"timeLabel": "19:00–21:00"}) is None


def test_lecturer_comes_from_module_and_facilitator_records_without_inventing():
    sessions = {s["id"]: s for s in schedule.sessions_from_collections(COLLECTIONS)}
    assert sessions["0_0"]["lecturer"] == "Dr D Mzinza"
    assert sessions["0_0"]["module_title"] == "Pregnancy and Neonatal Immunology"
    assert sessions["s-custom"]["lecturer"] == ""          # module says "Not specified" -> nothing invented


def test_custom_times_are_preserved_and_sorted():
    sessions = schedule.sessions_from_collections(COLLECTIONS)
    custom = next(s for s in sessions if s["id"] == "s-custom")
    assert (custom["start"], custom["end"]) == ("14:15", "16:05")
    keys = [(s["day"], s["start_min"]) for s in sessions]
    assert keys == sorted(keys)


def test_excel_workbook_is_valid_monday_to_friday_with_half_height_merged_lunch_row():
    import openpyxl
    payload = build_timetable_workbook(COLLECTIONS)
    assert payload[:2] == b"PK"                       # a real .xlsx (zip) container
    wb = openpyxl.load_workbook(io.BytesIO(payload))
    ws = wb["Weekly Timetable"]
    header = [str(c.value) for c in ws[3]][1:]
    assert [h.split("\n")[0] for h in header] == list(schedule.WEEKDAY_NAMES)
    assert "3rd Block" in str(ws["A1"].value)
    everything = " ".join(str(c.value) for sheet in wb for row in sheet.iter_rows() for c in row if c.value).lower()
    assert "saturday" not in everything and "sat," not in everything
    # The header band is the only merged part; the timetable itself is a plain grid.
    merged = {str(m) for m in ws.merged_cells.ranges}
    assert "A1:F1" in merged and "A2:F2" in merged
    body_merges = [m for m in merged if any(int(c) >= 4 for c in __import__("re").findall(r"[0-9]+", m))]
    assert body_merges == [], f"body cells must stay ordinary cells, found {body_merges}"
    lunch_rows = [r for r in range(4, ws.max_row + 1) if "lunch" in str(ws.cell(r, 1).value).replace(" ", "").lower()]
    assert len(lunch_rows) == 1
    r = lunch_rows[0]
    assert "12:00" in str(ws.cell(r, 1).value)
    assert ws.sheet_view.showGridLines is True
    text = "\n".join(str(c.value) for row in ws.iter_rows(min_row=4) for c in row if c.value)
    assert "PNIM-8100" in text and "Pregnancy and Neonatal Immunology" in text and "Dr D Mzinza" in text
    assert wb["Session Details"].auto_filter.ref


def test_database_migration_flags_but_never_deletes_non_weekday_records():
    from app.database import connection as conn_module
    original = (conn_module.DATABASE_PATH, conn_module.ensure_directories)
    with tempfile.TemporaryDirectory() as tmp:
        conn_module.DATABASE_PATH = Path(tmp) / "calendar.db"
        conn_module.ensure_directories = lambda: None
        try:
            first = conn_module.connect()
            first.execute("INSERT INTO docs(col,id,data,updated_at) VALUES('cells','old-sat',?,0)", (json.dumps({"dayIndex": 5, "startTime": "09:00", "endTime": "10:00", "code": "X"}),))
            first.execute("INSERT INTO docs(col,id,data,updated_at) VALUES('recurring','sat-club',?,0)", (json.dumps({"title": "Club", "day": "Saturday"}),))
            first.commit(); first.close()
            second = conn_module.connect()
            kept = {r["id"] for r in second.execute("SELECT id FROM docs WHERE id IN ('old-sat','sat-club')")}
            flagged = json.loads(second.execute("SELECT value FROM app_meta WHERE key='flagged_non_weekday_records'").fetchone()["value"])
            second.close()
        finally:
            conn_module.DATABASE_PATH, conn_module.ensure_directories = original
    assert kept == {"old-sat", "sat-club"}
    assert {f["id"] for f in flagged} == {"old-sat", "sat-club"}


def _clean_env(*names):
    saved = {n: os.environ.pop(n, None) for n in names}
    return saved


def _restore_env(saved):
    for k, v in saved.items():
        os.environ.pop(k, None)
        if v is not None:
            os.environ[k] = v


def test_server_binding_defaults_local_and_honours_platform_port():
    from app import config
    names = ("MNH_HOST", "MNH_PORT", "PORT", "MNH_LAN", "MNH_ENV", "RENDER")
    saved = _clean_env(*names)
    try:
        assert (config.server_host(), config.server_port()) == ("127.0.0.1", 8000)
        os.environ["PORT"] = "10000"; os.environ["MNH_ENV"] = "production"
        assert (config.server_host(), config.server_port()) == ("0.0.0.0", 10000)
        os.environ["MNH_PORT"] = "8001"
        assert config.server_port() == 8001
        os.environ.pop("MNH_ENV"); os.environ["MNH_LAN"] = "1"
        assert config.server_host() == "0.0.0.0"
    finally:
        _restore_env(saved)


def test_run_script_detects_a_port_that_is_already_in_use():
    if importlib.util.find_spec("uvicorn") is None:
        sys.modules.setdefault("uvicorn", types.ModuleType("uvicorn"))     # only the port probe is needed here
    spec = importlib.util.spec_from_file_location("mnh_run", ROOT / "backend" / "run.py")
    run = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(run)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as holder:
        holder.bind(("127.0.0.1", 0)); holder.listen(1)
        port = holder.getsockname()[1]
        assert run.port_is_free("127.0.0.1", port) is False
    assert run.port_is_free("127.0.0.1", port) is True


def test_service_worker_is_network_first_and_versions_match_everywhere():
    sw = (ROOT / "frontend" / "service-worker.js").read_text(encoding="utf-8")
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    config = (ROOT / "backend" / "app" / "config.py").read_text(encoding="utf-8")
    import re
    build = re.search(r'BUILD_ID = "([^"]+)"', config).group(1)
    assert f'const BUILD = "{build}"' in sw
    assert f'window.MNH_BUILD="{build}"' in html
    assert f"/js/app.js?v={build}" in html and f"/css/app.css?v={build}" in html
    assert "return cached || update" not in sw          # the old cache-first behaviour must be gone
    assert 'fetch(request, { cache: "no-store" })' in sw
