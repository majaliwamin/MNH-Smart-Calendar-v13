import base64
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image
from pptx import Presentation
from pptx.util import Inches
from reportlab.pdfgen import canvas

from app import config
from app.database import connection
from app.main import app
from app.services import backup_service

ROOT = Path(__file__).resolve().parents[1]
CLASSROOM = ROOT / "frontend" / "resources" / "crara-classroom"


def test_native_slide_navigation_assets_are_wired():
    html = (CLASSROOM / "index.html").read_text(encoding="utf-8")
    bundle = (CLASSROOM / "crara-classroom.js").read_text(encoding="utf-8")
    slides = (CLASSROOM / "crara-slides.js").read_text(encoding="utf-8")
    css = (CLASSROOM / "crara-classroom.css").read_text(encoding="utf-8")
    worker = (ROOT / "frontend" / "service-worker.js").read_text(encoding="utf-8")

    assert "crara-slides.js?v=crara-classroom-v10" in html
    assert 'data-crara-classroom-build="crara-classroom-v10"' in html
    assert "application/pdf,.pdf" in bundle
    assert "presentationml.presentation,.pptx" in bundle
    assert "PDF, PowerPoint (.pptx) or slide images" in bundle
    assert "window.__craraSlides={deck:l,session:s,goTo:Z}" in bundle

    assert "/api/class-rep/slides/render" in slides
    assert "cr-slide-panel" in slides
    assert "cr-slide-thumb" in slides
    assert "Collapse slide panel" in slides
    assert "Expand slide presentation" in slides
    assert "Restore classroom layout" in slides
    assert "Only the presenter can change slides" in slides
    assert "stagebarright" in slides

    assert ".presenter.cr-slides-active" in css
    assert ".cr-slide-list" in css
    assert ".cr-slide-thumb.active" in css
    assert "body.crara-slide-fullview" not in css  # class is scoped without the body type selector
    assert ".crara-slide-fullview .right" in css
    assert ".crara-slide-fullview .presenter" in css
    assert "@media(max-width:520px)" in css

    assert "/resources/crara-classroom/crara-slides.js" in worker

    for text in (html, bundle, slides, css):
        lowered = text.lower()
        assert "penrose" not in lowered
        assert "scholarmw" not in lowered
        assert "voice training" not in lowered
        assert "vtc" not in lowered
        assert "your logo" not in lowered
        assert "physics" not in lowered


def _storage(monkeypatch, tmp_path):
    database_dir = tmp_path / "database"
    monkeypatch.setattr(config, "DATABASE_DIR", database_dir)
    monkeypatch.setattr(config, "BACKUP_DIR", tmp_path / "backups")
    monkeypatch.setattr(connection, "DATABASE_PATH", database_dir / "calendar.db")
    monkeypatch.setattr(backup_service, "DATABASE_PATH", database_dir / "calendar.db")
    monkeypatch.setattr(backup_service, "BACKUP_DIR", tmp_path / "backups")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("MNH_ENV", "development")


def _pdf_bytes():
    output = BytesIO()
    page = canvas.Canvas(output, pagesize=(720, 405))
    page.drawString(36, 330, "Hypothesis Testing")
    page.showPage()
    page.save()
    return output.getvalue()


def _pptx_bytes():
    presentation = Presentation()
    presentation.slide_width = Inches(10)
    presentation.slide_height = Inches(7.5)
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(8), Inches(1))
    box.text_frame.text = "Sampling distribution"
    output = BytesIO()
    presentation.save(output)
    return output.getvalue()


def _image(body):
    data_url = body["slides"][0]["dataUrl"]
    assert data_url.startswith("data:image/jpeg;base64,")
    image = Image.open(BytesIO(base64.b64decode(data_url.split(",", 1)[1])))
    assert image.format == "JPEG"
    return image


def test_slide_render_endpoint_renders_pdf_and_pptx_pages(monkeypatch, tmp_path):
    _storage(monkeypatch, tmp_path)
    with TestClient(app) as client:
        client.cookies.set("cara_guest", "guest_slides_pdf_1234", path="/")
        pdf = client.post(
            "/api/class-rep/slides/render",
            files={"file": ("lesson.pdf", _pdf_bytes(), "application/pdf")},
        )
        assert pdf.status_code == 200
        body = pdf.json()
        assert body["format"] == "pdf"
        assert body["title"] == "lesson"
        assert body["count"] == 1
        image = _image(body)
        assert abs(image.width / image.height - 720 / 405) < 0.02

        deck = client.post(
            "/api/class-rep/slides/render",
            files={"file": (
                "theory.pptx",
                _pptx_bytes(),
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            )},
        )
        assert deck.status_code == 200
        body = deck.json()
        assert body["format"] == "pptx"
        assert body["count"] == 1
        image = _image(body)
        assert abs(image.width / image.height - 10 / 7.5) < 0.02


def test_slide_render_endpoint_rejects_unauthenticated_and_unsupported_files(monkeypatch, tmp_path):
    _storage(monkeypatch, tmp_path)
    with TestClient(app) as anonymous:
        assert anonymous.post(
            "/api/class-rep/slides/render",
            files={"file": ("lesson.pdf", _pdf_bytes(), "application/pdf")},
        ).status_code == 401

    with TestClient(app) as client:
        client.cookies.set("cara_guest", "guest_slides_errors_1234", path="/")
        legacy = client.post(
            "/api/class-rep/slides/render",
            files={"file": ("old.ppt", b"not a pptx", "application/vnd.ms-powerpoint")},
        )
        assert legacy.status_code == 400
        assert "pptx" in legacy.json()["error"]

        empty = client.post(
            "/api/class-rep/slides/render",
            files={"file": ("empty.pdf", b"", "application/pdf")},
        )
        assert empty.status_code == 400
        assert "empty" in empty.json()["error"].lower()
