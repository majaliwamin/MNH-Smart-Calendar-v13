from io import BytesIO

from app.class_rep.documents import _extract, DocumentError


def test_csv_and_svg_text_extraction():
    csv_data = b"Module,Date\nMNH 8100,2026-11-20\n"
    assert "MNH 8100" in _extract("schedule.csv", csv_data)[0][1]
    svg_data = b'<svg xmlns="http://www.w3.org/2000/svg"><text>Placental malaria</text></svg>'
    assert "Placental malaria" in _extract("diagram.svg", svg_data)[0][1]


def test_docx_pptx_and_xlsx_text_extraction():
    from docx import Document
    from pptx import Presentation
    from openpyxl import Workbook

    doc = Document()
    doc.add_paragraph("Word research notes")
    buffer = BytesIO()
    doc.save(buffer)
    assert "Word research notes" in _extract("notes.docx", buffer.getvalue())[0][1]

    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[5])
    slide.shapes.title.text = "Research presentation"
    buffer = BytesIO()
    presentation.save(buffer)
    assert "Research presentation" in _extract("slides.pptx", buffer.getvalue())[0][1]

    workbook = Workbook()
    workbook.active["A1"] = "Placental biomarkers"
    buffer = BytesIO()
    workbook.save(buffer)
    assert "Placental biomarkers" in _extract("data.xlsx", buffer.getvalue())[0][1]


def test_unsupported_legacy_office_format_is_rejected_clearly():
    try:
        _extract("legacy.doc", b"not a doc")
    except DocumentError as exc:
        assert "not supported" in str(exc)
    else:
        raise AssertionError("Legacy binary DOC files must not be silently accepted")



def test_ingest_falls_back_to_keyword_index_when_embeddings_are_unavailable(monkeypatch):
    from contextlib import contextmanager
    from app.class_rep import documents

    statements = []

    class FakeConnection:
        def execute(self, statement, parameters=()):
            statements.append((statement, parameters))

    @contextmanager
    def fake_database():
        yield FakeConnection()

    def unavailable_embeddings(*args, **kwargs):
        raise AssertionError("Remote embeddings must not block document upload")

    monkeypatch.setattr(documents, "database", fake_database)
    monkeypatch.setattr(documents, "_vectors", unavailable_embeddings)
    result = documents.ingest("notes.txt", b"Placental malaria research notes", owner_id="test-user")
    assert result["chunks"] == 1
    assert result["view_url"].endswith("/file")
    assert len(statements) == 3
    assert any("cara_document_files" in statement for statement, _ in statements)


def test_document_uploads_remain_enabled_without_embedding_credentials(monkeypatch):
    from app.class_rep.routes import status

    monkeypatch.delenv("MNH_CLASSREP_CLOUDFLARE_API_KEY", raising=False)
    monkeypatch.delenv("MNH_CLASSREP_CLOUDFLARE_ACCOUNT_ID", raising=False)
    result = status()
    assert result["document_uploads"] == "enabled"
    assert result["document_search"] == "keyword_only"
