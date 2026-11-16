"""Optional CPU OCR adapters for scanned PDF pages and image uploads.

Install with: pip install -r backend/requirements-ocr.txt
MNH_CLASSREP_OCR_ENGINE=auto (PaddleOCR first, then EasyOCR), paddleocr, or easyocr.
"""
import os
from functools import lru_cache
from io import BytesIO


class OCRDocumentError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _easy_reader():
    try:
        import easyocr
        return easyocr.Reader(["en"], gpu=False, verbose=False)
    except ImportError as exc:
        raise OCRDocumentError("EasyOCR is unavailable. Install backend/requirements-ocr.txt.") from exc


@lru_cache(maxsize=1)
def _paddle_reader():
    try:
        from paddleocr import PaddleOCR
    except ImportError as exc:
        raise OCRDocumentError("PaddleOCR is unavailable. Install backend/requirements-ocr.txt.") from exc
    try:
        return PaddleOCR(lang="en", device="cpu", use_doc_orientation_classify=False,
                         use_doc_unwarping=False, use_textline_orientation=False)
    except TypeError:
        return PaddleOCR(lang="en", use_angle_cls=True, show_log=False)


def _engine_order(engine: str | None = None) -> list[str]:
    selected = (engine or os.getenv("MNH_CLASSREP_OCR_ENGINE", "auto")).strip().lower()
    if selected == "auto":
        return ["paddleocr", "easyocr"]
    if selected in {"paddleocr", "easyocr"}:
        return [selected]
    raise OCRDocumentError("MNH_CLASSREP_OCR_ENGINE must be auto, paddleocr or easyocr.")


def _texts(value):
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if not isinstance(value, (str, dict, list, tuple)) and hasattr(value, "json"):
        try:
            return _texts(value.json)
        except Exception:
            return []
    if isinstance(value, dict):
        if isinstance(value.get("res"), dict):
            return _texts(value["res"])
        for key in ("rec_texts", "texts", "text"):
            if key in value:
                return _texts(value[key])
        return []
    if isinstance(value, (list, tuple)):
        # PaddleOCR 2.x and EasyOCR individual detections have a polygon first.
        # A plain list of recognised strings (PaddleOCR 3.x) must be traversed.
        if (len(value) >= 2 and isinstance(value[0], (list, tuple))
                and value[0] and isinstance(value[0][0], (list, tuple))
                and isinstance(value[1], str)):
            return [value[1].strip()] if value[1].strip() else []
        if (len(value) >= 2 and isinstance(value[0], (list, tuple))
                and value[0] and isinstance(value[0][0], (list, tuple))
                and isinstance(value[1], (list, tuple)) and value[1]
                and isinstance(value[1][0], str)):
            return [value[1][0].strip()] if value[1][0].strip() else []
        result = []
        for item in value:
            result.extend(_texts(item))
        return result
    return []


def _ocr_image(image):
    import numpy as np
    engines = _engine_order()
    array = np.asarray(image.convert("RGB"))
    failures = []
    for name in engines:
        try:
            if name == "paddleocr":
                reader = _paddle_reader()
                result = reader.predict(input=array) if hasattr(reader, "predict") else reader.ocr(array, cls=True)
            else:
                result = _easy_reader().readtext(array, detail=1, paragraph=False)
            text = "\n".join(filter(None, _texts(result))).strip()
            if text:
                return text
            failures.append(name + " returned no text")
        except OCRDocumentError as exc:
            failures.append(str(exc))
        except Exception:
            failures.append(name + " could not process this page")
    raise OCRDocumentError("OCR could not read this page. " + " ".join(failures))


def extract_image(content: bytes) -> str:
    try:
        from PIL import Image
        with Image.open(BytesIO(content)) as image:
            return _ocr_image(image)
    except OCRDocumentError:
        raise
    except Exception as exc:
        raise OCRDocumentError("The image could not be opened for OCR.") from exc


def extract_pdf(content: bytes) -> list[tuple[int, str]]:
    try:
        import pypdfium2 as pdfium
        from pypdf import PdfReader
        reader = PdfReader(BytesIO(content))
        if len(reader.pages) > 40:
            raise OCRDocumentError("PDFs are limited to 40 pages for scanned-page OCR.")
        rendered = pdfium.PdfDocument(content)
        pages = []
        for index, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if len("".join(text.split())) < 25:
                bitmap = rendered[index].render(scale=2.0)
                text = (text + "\n" + _ocr_image(bitmap.to_pil())).strip()
            if text.strip():
                pages.append((index + 1, text))
        return pages
    except OCRDocumentError:
        raise
    except ImportError as exc:
        raise OCRDocumentError("PDF rendering support is unavailable. Install backend/requirements.txt.") from exc
    except Exception as exc:
        raise OCRDocumentError("The PDF could not be rendered for OCR. It may be encrypted or damaged.") from exc
