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
