"""Render presentation documents into classroom slide images.

The Live Classroom already distributes normalized JPEG slide pages over its
existing LiveKit data channel. This module only converts PDF/PPTX uploads into
those pages; it does not create a second presentation system.
"""
from __future__ import annotations

import base64
import io
import re

from PIL import Image, ImageDraw, ImageFont

MAX_SLIDES = 60
MAX_UPLOAD_BYTES = 15 * 1024 * 1024
TARGET_WIDTH = 1280
TARGET_HEIGHT = 720
EMU_PER_INCH = 914400

_PDF_MIME = "application/pdf"
_PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
_LEGACY_PPT_MIME = "application/vnd.ms-powerpoint"


class SlideImportError(RuntimeError):
    pass


def _document_kind(filename: str, content_type: str) -> str:
    lower_name = (filename or "").lower()
    lower_type = (content_type or "").lower().split(";", 1)[0].strip()
    if lower_type == _PDF_MIME or lower_name.endswith(".pdf"):
        return "pdf"
    if lower_type == _LEGACY_PPT_MIME or lower_name.endswith(".ppt"):
        raise SlideImportError(
            "Legacy .ppt files are not supported. Save the presentation as .pptx and try again."
        )
    if lower_type == _PPTX_MIME or lower_name.endswith(".pptx"):
        return "pptx"
    raise SlideImportError(
        "Use a PDF or PowerPoint (.pptx) presentation, or choose PNG, JPEG or WebP slide images."
    )


def _jpeg(image: Image.Image) -> bytes:
    output = io.BytesIO()
    image.convert("RGB").save(output, format="JPEG", quality=84, optimize=True)
    return output.getvalue()


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = (
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    )
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def _rgb(value, default=(24, 28, 38)) -> tuple[int, int, int] | None:
    try:
        rgb = value.rgb
        return int(rgb[0]), int(rgb[1]), int(rgb[2])
    except (AttributeError, TypeError, ValueError):
        return default


def _shape_fill_rgb(shape) -> tuple[int, int, int] | None:
    try:
        fill = shape.fill
        if fill.type is None or fill.fore_color.type is None:
            return None
        return _rgb(fill.fore_color, None)
    except (AttributeError, TypeError, ValueError):
        return None


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font, width: int) -> list[str]:
    words = re.findall(r"\S+\s*", text or "")
    if not words:
        return [""]
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = current + word
        if current and draw.textlength(candidate.strip(), font=font) > width:
            lines.append(current.rstrip())
            current = word.strip() + " "
        else:
            current = candidate
    if current.strip():
        lines.append(current.rstrip())
    return lines or [""]


def _draw_text_frame(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int],
                     text_frame, pixels_per_point: float) -> None:
    left, top, right, bottom = box
    if right <= left or bottom <= top:
        return
    y = top + 4
    for paragraph in text_frame.paragraphs:
        runs = list(getattr(paragraph, "runs", []) or [])
        text = "".join(str(run.text or "") for run in runs) or str(paragraph.text or "")
        if not text.strip():
            y += max(8, int(18 * pixels_per_point))
            continue
        first_run = runs[0] if runs else None
        try:
            point_size = float(first_run.font.size.pt) if first_run and first_run.font.size else 18.0
        except (AttributeError, TypeError, ValueError):
            point_size = 18.0
        point_size = min(72.0, max(9.0, point_size))
        font = _font(max(11, int(round(point_size * pixels_per_point))),
                     bool(first_run and first_run.font.bold))
        color = _rgb(first_run.font.color, (24, 28, 38)) or (24, 28, 38)
        prefix = "• " if getattr(paragraph, "level", 0) else ""
        for line in _wrap_text(draw, prefix + text.strip(), font, max(20, right - left - 12)):
            if y + 4 > bottom:
                return
            draw.text((left + 6, y), line, font=font, fill=color)
            y += max(11, int(font.size * 1.25))


def _render_pptx(content: bytes) -> list[bytes]:
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    try:
        presentation = Presentation(io.BytesIO(content))
    except Exception as exc:  # python-pptx raises several parser-specific errors
        raise SlideImportError("The PowerPoint file could not be opened.") from exc

    if not presentation.slides:
        raise SlideImportError("The PowerPoint file has no slides.")
    if len(presentation.slides) > MAX_SLIDES:
        raise SlideImportError(f"Present at most {MAX_SLIDES} slides at a time.")

    slide_width = max(1, int(presentation.slide_width or 1))
    slide_height = max(1, int(presentation.slide_height or 1))
    scale = min(TARGET_WIDTH / slide_width, TARGET_HEIGHT / slide_height)
    width = max(1, int(round(slide_width * scale)))
    height = max(1, int(round(slide_height * scale)))
    pixels_per_point = scale * EMU_PER_INCH / 72.0

    def box(shape) -> tuple[int, int, int, int]:
        left = int(max(0, min(width - 1, (shape.left or 0) * scale)))
        top = int(max(0, min(height - 1, (shape.top or 0) * scale)))
        right = int(max(left + 1, min(width, left + (shape.width or 0) * scale)))
        bottom = int(max(top + 1, min(height, top + (shape.height or 0) * scale)))
        return left, top, right, bottom

    pages: list[bytes] = []
    for slide in presentation.slides:
        image = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(image)
        fill = _shape_fill_rgb(slide.background)
        if fill:
            draw.rectangle((0, 0, width, height), fill=fill)

        for shape in slide.shapes:
            left, top, right, bottom = box(shape)
            background = _shape_fill_rgb(shape)
            if background and not getattr(shape, "has_text_frame", False):
                draw.rectangle((left, top, right, bottom), fill=background)

        for shape in slide.shapes:
            left, top, right, bottom = box(shape)
            if getattr(shape, "shape_type", None) == MSO_SHAPE_TYPE.PICTURE:
                try:
                    picture = Image.open(io.BytesIO(shape.image.blob)).convert("RGB")
                    picture = picture.resize((max(1, right - left), max(1, bottom - top)))
                    image.paste(picture, (left, top))
                except Exception:
                    draw.rectangle((left, top, right, bottom), outline=(190, 190, 200), width=2)
                continue
            if getattr(shape, "has_table", False):
                table = shape.table
                rows = max(1, len(table.rows))
                cols = max(1, len(table.columns))
                cell_w = max(1, (right - left) // cols)
                cell_h = max(1, (bottom - top) // rows)
                for row in range(rows):
                    for col in range(cols):
                        x0 = left + col * cell_w
                        y0 = top + row * cell_h
                        draw.rectangle((x0, y0, x0 + cell_w, y0 + cell_h),
                                       outline=(170, 175, 190), width=1)
                        try:
                            text = str(table.cell(row, col).text or "")
                        except (AttributeError, IndexError):
                            text = ""
                        if text:
                            font = _font(max(11, int(round(15 * pixels_per_point))))
                            draw.text((x0 + 5, y0 + 4), text[:140], font=font, fill=(24, 28, 38))
                continue
            if getattr(shape, "has_text_frame", False) and shape.text_frame.text.strip():
                _draw_text_frame(draw, (left, top, right, bottom),
                                 shape.text_frame, pixels_per_point)
        pages.append(_jpeg(image))
    return pages


def _render_pdf(content: bytes) -> list[bytes]:
    import pypdfium2 as pdfium

    try:
        document = pdfium.PdfDocument(content)
    except Exception as exc:
        raise SlideImportError("The PDF file could not be opened.") from exc
    if len(document) == 0:
        raise SlideImportError("The PDF file has no pages.")
    if len(document) > MAX_SLIDES:
        raise SlideImportError(f"Present at most {MAX_SLIDES} pages at a time.")

    pages: list[bytes] = []
    for index in range(len(document)):
        try:
            page = document[index]
            width, height = page.get_size()
            scale = min(TARGET_WIDTH / max(1.0, float(width)),
                        TARGET_HEIGHT / max(1.0, float(height)))
            bitmap = page.render(scale=scale)
            pages.append(_jpeg(bitmap.to_pil()))
        except Exception as exc:
            raise SlideImportError(f"PDF page {index + 1} could not be rendered.") from exc
    return pages


def render_presentation(filename: str, content_type: str, content: bytes) -> dict:
    if not content:
        raise SlideImportError("The presentation file is empty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise SlideImportError("Presentation files must be 15 MB or smaller.")
    kind = _document_kind(filename, content_type)
    pages = _render_pdf(content) if kind == "pdf" else _render_pptx(content)
    title = re.sub(r"\.[^.]+$", "", filename or "Presentation").strip() or "Presentation"
    return {
        "title": title[:120],
        "format": kind,
        "count": len(pages),
        "slides": [
            {
                "name": f"slide-{index + 1:03d}.jpg",
                "dataUrl": "data:image/jpeg;base64," + base64.b64encode(page).decode("ascii"),
            }
            for index, page in enumerate(pages)
        ],
    }
