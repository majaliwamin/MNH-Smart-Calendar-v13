import base64
import json
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
RESOURCE_MANIFEST = CLASSROOM / "crara-resources.json"
BUNDLED_DECK = CLASSROOM / "files" / "amr-maternal-neonatal-malawi"


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
    assert 'className:"stagefile"' in bundle
    assert "No shared screen or slides yet" not in bundle
    assert "Annotations stay attached to each slide" not in bundle
    assert "window.__craraSlides={deck:l,session:s,goTo:Z,stopSlides:()=>s.stopSlides()}" in bundle
    assert "__craraShare=window.__craraSlideShare" in bundle
    assert 'source:__craraFromCrara?"crara":""' in bundle
    assert 'source:B.source||""' in bundle
    assert 'source:Fe.source||""' in bundle
    assert 'source:H.source||""' in bundle
    assert "us=O.useCallback((B,__craraSender)" in bundle
    assert "__craraSender!==B.owner" in bundle
    assert "tt&&us(tt,__craraSender&&__craraSender.identity)" in bundle
    assert "G.ctrlKey||G.metaKey||G.altKey||G.isComposing" in bundle
    assert 'n.closest("input,select,textarea,button,a[href]' in bundle

    assert "/api/class-rep/slides/render" in slides
    assert "cr-slide-panel" in slides
    assert "cr-slide-thumb" in slides
    assert "Collapse slide panel" in slides
    assert "Expand slide presentation" in slides
    assert "Restore classroom layout" in slides
    assert "Only the presenter can change slides" in slides
    assert "stagebarright" in slides
    assert ".cr-slide-import" in slides
    assert '"Present slides"' in slides
    assert "cr-slide-import-status" in slides
    assert "cr-files-panel" in slides
    assert "Add files from device" in slides
    assert "Shared by CRARA" in slides
    assert "Stop sharing" in slides
    assert "activeTabName() === \"Files\"" in slides
    assert "crara-resources.json" in slides
    assert "CRARA resources" in slides
    assert "Share in room" in slides
    assert "View chapters" in slides
    assert "licensed chapter text" in slides
    assert "window.__craraSlideShare" in slides
    assert "deck.source === CRARA_SOURCE" in slides
    assert "Boolean(sharedResourceId)" not in slides
    assert "resourcesError" in slides
    assert "applyFullViewClass" in slides
    assert "document.fullscreenElement === presenter" in slides
    assert "applyingUpdate" in slides

    assert ".presenter.cr-slides-active" in css
    assert ".right.cr-files-active>.empty" in css
    assert ".cr-files-panel" in css
    assert ".cr-file-add" in css
    assert ".cr-resource-card" in css
    assert ".cr-resource-honesty" in css
    assert ".cr-slide-import" in css
    assert ".cr-slide-list" in css
    assert ".cr-slide-thumb.active" in css
    assert "body.crara-slide-fullview" not in css  # class is scoped without the body type selector
    assert ".crara-slide-fullview .right" in css
    assert ".crara-slide-fullview .presenter" in css
    assert "@media(max-width:520px)" in css

    assert "/resources/crara-classroom/crara-slides.js" in worker
    assert "/resources/crara-classroom/crara-resources.json" in worker
    assert "/resources/crara-classroom/files/amr-maternal-neonatal-malawi/slides.json" in worker
    assert "/resources/crara-classroom/files/amr-maternal-neonatal-malawi/slide-028.jpg" in worker

    for text in (html, bundle, slides, css):
        lowered = text.lower()
        assert "penrose" not in lowered
        assert "scholarmw" not in lowered
        assert "voice training" not in lowered
        assert "vtc" not in lowered
        assert "your logo" not in lowered
        assert "physics" not in lowered


def test_bundled_crara_resources_include_lecture_deck_and_honest_book_outlines():
    manifest = json.loads(RESOURCE_MANIFEST.read_text(encoding="utf-8"))
    assert manifest["schemaVersion"] == 1
    by_id = {item["id"]: item for item in manifest["resources"]}

    deck = by_id["amr-maternal-neonatal-malawi"]
    assert deck["kind"] == "deck"
    assert deck["category"] == "Lecture notes"
    assert deck["title"] == "Antimicrobial Resistance in Maternal and Neonatal Health in Malawi"
    assert deck["slides"] == 28
    source = CLASSROOM / "files" / "amr-maternal-neonatal-malawi.pptx"
    assert source.is_file() and source.stat().st_size > 50_000

    payload = json.loads((BUNDLED_DECK / "slides.json").read_text(encoding="utf-8"))
    assert payload["count"] == 28
    assert len(payload["slides"]) == 28
    for index, entry in enumerate(payload["slides"], start=1):
        assert entry["name"] == f"slide-{index:03d}.jpg"
        image_path = BUNDLED_DECK / entry["name"]
        assert image_path.is_file()
        with Image.open(image_path) as image:
            image.verify()

    book = by_id["regression-methods-chapter-outlines"]
    assert book["kind"] == "chapters"
    assert "licensed chapter text" in book["summary"].lower()
    assert len(book["book"]["chapters"]) == 13
    assert "Licensed text" in book["book"]["accessNoteEn"]
    assert "chapter outline only" in book["book"]["accessNoteEn"]
    assert "utm_source=chatgpt.com" not in book["book"]["url"]

    lowered = RESOURCE_MANIFEST.read_text(encoding="utf-8").lower()
    for term in ("penrose", "scholarmw", "voice training", "vtc", "your logo", "physics"):
        assert term not in lowered


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
