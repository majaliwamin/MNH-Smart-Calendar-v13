"""Fillable PDF timetable (AcroForm) built with reportlab — pure function, no web framework.

"Fully editable": every session cell, module field and register row is a real
PDF form field. The user opens the file in any PDF reader (Acrobat, Edge,
Chrome), types directly into the cells, saves, and the file is ready to share.

Layout (A4 landscape):
  page 1  Weekly Timetable grid — one editable field per session slot per day
  page 2  Module Directory — editable code / title / facilitator per selected module
  page 3+ Session Register — editable rows for every scheduled session
"""
from datetime import timedelta
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from app.services.schedule import WEEK_START, WEEKDAY_NAMES, clock, overlaps_lunch, sessions_from_collections
from app.services.excel_export import module_catalogue, normalise_selection

TITLE = "PhD in Maternal and Neonatal Health : 3rd Block"
NAVY = colors.HexColor("#102B4E")
BLUE = colors.HexColor("#1F497D")
PALE = colors.HexColor("#EAF1F8")
LINE = colors.HexColor("#9DB2C8")

TIME_SLOTS = [(8, 10), (10, 12), (12, 13.5), (13.5, 15.5), (15.5, 17.5), (17.5, 19), (19, 21)]

_CHAR_MAP = {0x2013: "-", 0x2014: "-", 0x2018: "'", 0x2019: "'", 0x201C: '"', 0x201D: '"', 0x00A0: " ", 0x2026: "..."}


def _ascii(text) -> str:
    """PDF form fields render their appearance with a Latin-1-safe encoder; map the
    few typographic characters we use (en-dash in 'ARMN – 8100' etc.) to safe ones."""
    return str(text or "").translate(_CHAR_MAP).encode("latin-1", "replace").decode("latin-1")


def _slot_label(hours_start, hours_end) -> str:
    return f"{clock(int(hours_start * 60))}–{clock(int(hours_end * 60))}"


def build_timetable_pdf(collections: dict, selected_modules: list | None = None) -> bytes:
    sessions = sessions_from_collections(collections)
    selection = normalise_selection(selected_modules, collections)
    catalogue = {m["code"]: m for m in module_catalogue(collections)}

    out = BytesIO()
    page = landscape(A4)
    width, height = page
    pdf = canvas.Canvas(out, pagesize=page)
    pdf.setTitle(f"{TITLE} — Editable Timetable")
    pdf.setAuthor("MNH Smart Calendar")

    def banner(subtitle: str) -> float:
        pdf.setFillColor(NAVY)
        pdf.rect(0, height - 16 * mm, width, 16 * mm, stroke=0, fill=1)
        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(10 * mm, height - 11 * mm, f"{TITLE} — Editable Timetable")
        pdf.setFont("Helvetica", 9)
        pdf.drawRightString(width - 10 * mm, height - 11 * mm, subtitle)
        return height - 16 * mm

    def note(text: str, y: float) -> float:
        pdf.setFillColor(colors.HexColor("#33475B"))
        pdf.setFont("Helvetica-Oblique", 8)
        pdf.drawString(10 * mm, y, text)
        return y - 5 * mm

    # ============================ page 1: weekly grid ============================
    top = banner("Weekly Timetable · week commencing " + WEEK_START.strftime("%d %b %Y") + " · type in any cell")
    top = note("This PDF is a fillable form: click a white cell and type. Save the file to keep your edits.", top)
    grid_top = top - 4 * mm
    label_w = 30 * mm
    day_w = (width - 20 * mm - label_w) / 5
    header_h = 9 * mm
    row_h = min((grid_top - header_h - 15 * mm) / len(TIME_SLOTS), 26 * mm)

    # day headers
    for i, name in enumerate(WEEKDAY_NAMES):
        x = 10 * mm + label_w + i * day_w
        pdf.setFillColor(BLUE)
        pdf.rect(x, grid_top - header_h, day_w, header_h, stroke=1, fill=1)
        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawCentredString(x + day_w / 2, grid_top - header_h + 3 * mm,
                              f"{name}  {(WEEK_START + timedelta(days=i)).strftime('%d %b')}")
    # time rows + editable session fields
    form = pdf.acroForm
    y = grid_top - header_h
    for (hs, he) in TIME_SLOTS:
        y -= row_h
        pdf.setFillColor(PALE)
        pdf.rect(10 * mm, y, label_w, row_h, stroke=1, fill=1)
        pdf.setFillColor(NAVY)
        pdf.setFont("Helvetica-Bold", 8)
        label = _slot_label(hs, he)
        pdf.drawCentredString(10 * mm + label_w / 2, y + row_h / 2 - 1 * mm, label)
        if abs(hs - 12) < 0.01:  # lunch row
            pdf.setFillColor(colors.HexColor("#F6E7C1"))
            for i in range(5):
                x = 10 * mm + label_w + i * day_w
                pdf.rect(x, y, day_w, row_h, stroke=1, fill=1)
            pdf.setFillColor(NAVY)
            pdf.setFont("Helvetica-Bold", 9)
            pdf.drawCentredString(10 * mm + label_w + day_w * 2.5, y + row_h / 2 - 1 * mm, "Lunch Break")
            continue
        for i, name in enumerate(WEEKDAY_NAMES):
            x = 10 * mm + label_w + i * day_w
            match = [s for s in sessions
                     if s["weekday"] == name and s["start_min"] == int(hs * 60) and s["end_min"] == int(he * 60)]
            pdf.setStrokeColor(LINE)
            pdf.rect(x, y, day_w, row_h, stroke=1, fill=0)
            preset = ""
            if match:
                s = match[0]
                preset = "\n".join(filter(None, [s["code"], s["lecturer"], s["activity"] if s["activity"] != s["code"] else ""]))[:200]
            field_h = row_h - 2 * mm
            form.textfield(name=f"wk_{i}_{int(hs*60)}", tooltip=f"{name} {label}",
                           x=x + 1 * mm, y=y + 1 * mm, width=day_w - 2 * mm, height=field_h,
                           fontSize=7, value=_ascii(preset), borderWidth=0,
                           fillColor=colors.HexColor("#FDFDFD"), textColor=colors.black,
                           fieldFlags='multiline')
    pdf.showPage()

    # ============================ page 2: module directory ============================
    top = banner("Module Directory · the modules included in this export")
    top = note("Edit the module details directly in the form fields; use the blank block to add another module.", top)
    col_x = [10 * mm, 60 * mm, 145 * mm, 215 * mm]
    col_w = [48 * mm, 83 * mm, 68 * mm, width - 215 * mm - 10 * mm]
    headers = ["Module code", "Module title", "Facilitator", "Sessions this week"]
    pdf.setFillColor(BLUE)
    pdf.rect(10 * mm, top - 9 * mm, width - 20 * mm, 9 * mm, stroke=1, fill=1)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 10)
    for x, w, text in zip(col_x, col_w, headers):
        pdf.drawString(x + 2 * mm, top - 6.5 * mm, text)
    y = top - 9 * mm
    week_counts = {}
    for s in sessions:
        week_counts[s["code"]] = week_counts.get(s["code"], 0) + 1
    rows = [catalogue.get(code, {"code": code, "title": "", "facilitator": ""}) for code in selection]
    rows += [{"code": "", "title": "", "facilitator": ""}] * 3  # blank editable rows
    for idx, module in enumerate(rows):
        y -= 12 * mm
        pdf.setStrokeColor(LINE)
        for i in range(4):
            pdf.rect(col_x[i], y, col_w[i], 12 * mm, stroke=1, fill=0)
        form.textfield(name=f"mod_{idx}_code", tooltip="Module code", x=col_x[0] + 1.5 * mm, y=y + 2 * mm,
                       width=col_w[0] - 3 * mm, height=8 * mm, fontSize=9, value=_ascii(module.get("code"))[:60],
                       borderWidth=0, fillColor=colors.HexColor("#FDFDFD"), textColor=colors.black)
        form.textfield(name=f"mod_{idx}_title", tooltip="Module title", x=col_x[1] + 1.5 * mm, y=y + 2 * mm,
                       width=col_w[1] - 3 * mm, height=8 * mm, fontSize=9, value=_ascii(module.get("title"))[:120],
                       borderWidth=0, fillColor=colors.HexColor("#FDFDFD"), textColor=colors.black)
        form.textfield(name=f"mod_{idx}_facilitator", tooltip="Facilitator", x=col_x[2] + 1.5 * mm, y=y + 2 * mm,
                       width=col_w[2] - 3 * mm, height=8 * mm, fontSize=9, value=_ascii(module.get("facilitator"))[:80],
                       borderWidth=0, fillColor=colors.HexColor("#FDFDFD"), textColor=colors.black)
        pdf.setFillColor(colors.black)
        pdf.setFont("Helvetica", 10)
        pdf.drawString(col_x[3] + 2 * mm, y + 4.5 * mm, str(week_counts.get(module.get("code", ""), 0) or 0) if module.get("code") else "")
    pdf.showPage()

    # ============================ page 3+: session register ============================
    reg_cols = [("Date", 26 * mm), ("Time", 24 * mm), ("Module code", 30 * mm), ("Lecturer", 34 * mm),
                ("Activity / topic", 70 * mm), ("Delivery mode", 26 * mm), ("Status", 24 * mm), ("Notes", 96 * mm)]
    reg_x, reg_w, i = [], [], 0
    x = 10 * mm
    for _, w in reg_cols:
        reg_x.append(x); reg_w.append(w); x += w
    while True:
        top = banner("Session Register · editable rows")
        top = note("One row per session; type over any field. Continue on your own copy if more rows are needed.", top)
        pdf.setFillColor(BLUE)
        pdf.rect(10 * mm, top - 8 * mm, width - 20 * mm, 8 * mm, stroke=1, fill=1)
        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 9)
        for cx, cw, (name, _) in zip(reg_x, reg_w, reg_cols):
            pdf.drawString(cx + 1.5 * mm, top - 5.5 * mm, name)
        y = top - 8 * mm
        page_rows = int((y - 15 * mm) // (10 * mm))
        chunk = sessions[i:i + page_rows]
        for r_idx, s in enumerate(chunk):
            y -= 10 * mm
            pdf.setStrokeColor(LINE)
            for cidx in range(len(reg_cols)):
                pdf.rect(reg_x[cidx], y, reg_w[cidx], 10 * mm, stroke=1, fill=0)
            values = [s["date"].strftime("%a %d %b"), f"{s['start']}–{s['end']}", s["code"], s["lecturer"],
                      s["activity"] if s["activity"] != s["code"] else "", s["mode"], s["status"], s["notes"]]
            for cidx, value in enumerate(values):
                form.textfield(name=f"reg_{i + r_idx}_{cidx}", tooltip=reg_cols[cidx][0],
                               x=reg_x[cidx] + 1 * mm, y=y + 1.5 * mm, width=reg_w[cidx] - 2 * mm, height=7 * mm,
                               fontSize=7, value=_ascii(value)[:150], borderWidth=0,
                               fillColor=colors.HexColor("#FDFDFD"), textColor=colors.black)
        i += len(chunk)
        if not chunk or i >= len(sessions):
            break
        pdf.showPage()
    if not sessions:
        # still emit the register header page so the document is complete
        pass

    pdf.save()
    return out.getvalue()


__all__ = ["build_timetable_pdf"]
