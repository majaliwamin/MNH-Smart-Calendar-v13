"""Export tests: module selection, editable Excel, fillable PDF."""
import json

import pytest
from fastapi.testclient import TestClient

from app import config
from app.database import connection
from app.main import app
from app.services import authentication
from app.services.excel_export import DEFAULT_MODULES, build_timetable_workbook, module_catalogue, normalise_selection
from app.services.pdf_export import build_timetable_pdf


def configure_test_storage(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DATABASE_DIR", tmp_path / "database")
    monkeypatch.setattr(connection, "DATABASE_PATH", tmp_path / "database" / "calendar.db")
    monkeypatch.setenv("MNH_ENV", "development")
    authentication.SESSIONS.clear()


@pytest.fixture()
def client(monkeypatch, tmp_path):
    configure_test_storage(monkeypatch, tmp_path)
    with TestClient(app) as test_client:
        yield test_client


# ---- module catalogue ------------------------------------------------------
def test_catalogue_always_contains_the_three_programme_modules():
    catalogue = module_catalogue({})
    codes = [m["code"] for m in catalogue]
    assert "ARMN – 8100" in codes and "MIPN 8100" in codes and "PNIM-8100" in codes


def test_default_selection_is_the_three_programme_modules():
    assert normalise_selection(None, {}) == [m["code"] for m in DEFAULT_MODULES]
    assert normalise_selection(["PNIM-8100", "bogus-999"], {}) == ["PNIM-8100"]


# ---- Excel ---------------------------------------------------------------
def test_excel_contains_module_directory_and_defaults():
    payload = build_timetable_workbook({})
    from io import BytesIO
    from openpyxl import load_workbook
    wb = load_workbook(BytesIO(payload))
    assert "Module Directory" in wb.sheetnames
    directory = wb["Module Directory"]
    codes = [directory.cell(row, 1).value for row in range(3, 6)]
    assert codes == [m["code"] for m in DEFAULT_MODULES]


def test_excel_honours_a_custom_selection():
    payload = build_timetable_workbook({}, ["PNIM-8100"])
    from io import BytesIO
    from openpyxl import load_workbook
    wb = load_workbook(BytesIO(payload))
    directory = wb["Module Directory"]
    assert directory.cell(3, 1).value == "PNIM-8100"
    assert directory.cell(4, 1).value is None  # only the selected module listed


# ---- PDF -----------------------------------------------------------------
def test_pdf_is_a_fillable_acroform_document():
    payload = build_timetable_pdf({})
    assert payload.startswith(b"%PDF")
    assert b"/AcroForm" in payload          # fillable form
    assert b"Antimicrobial Resistance" in payload  # the three modules are present
    assert b"Medical Imaging" in payload
    assert b"Pregnancy and Neonatal Immunology" in payload


def test_pdf_selection_changes_the_module_directory():
    payload = build_timetable_pdf({}, ["MIPN 8100"])
    assert b"MIPN 8100" in payload
    assert b"Pregnancy and Neonatal Immunology" not in payload


# ---- API -------------------------------------------------------------------
def test_export_endpoints_serve_the_selection(client):
    xlsx = client.get("/api/export/timetable.xlsx")
    assert xlsx.status_code == 200 and xlsx.content[:2] == b"PK"
    pdf = client.get("/api/export/timetable.pdf", params={"modules": "MIPN 8100"})
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    listed = client.get("/api/export/modules").json()
    codes = [m["code"] for m in listed["modules"]]
    assert {"ARMN – 8100", "MIPN 8100", "PNIM-8100"} <= set(codes)
