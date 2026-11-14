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
from reportlab.lib.pagesizes import A3, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from app.services.schedule import WEEK_START, WEEKDAY_NAMES, clock, overlaps_lunch, sessions_from_collections
from app.services.excel_export import module_catalogue, normalise_selection

TITLE = "PhD in Maternal and Neonatal Health : 3rd Block"
APP_NAME = "MNH Smart Calendar"
APP_SUBTITLE = "Academic Calendar"
NAVY = colors.HexColor("#102B4E")
BLUE = colors.HexColor("#1F497D")
PALE = colors.HexColor("#EAF1F8")
LINE = colors.HexColor("#9DB2C8")

TIME_SLOTS = [(8, 10), (10, 12), (12, 13.5), (13, 14), (13.5, 15.5), (15.5, 17.5), (17.5, 19), (19, 21)]

_CHAR_MAP = {0x2013: "-", 0x2014: "-", 0x2018: "'", 0x2019: "'", 0x201C: '"', 0x201D: '"', 0x00A0: " ", 0x2026: "..."}


def _ascii(text) -> str:
    """PDF form fields render their appearance with a Latin-1-safe encoder; map the
    few typographic characters we use (en-dash in 'ARMN – 8100' etc.) to safe ones."""
    return str(text or "").translate(_CHAR_MAP).encode("latin-1", "replace").decode("latin-1")


def _slot_label(hours_start, hours_end) -> str:
    return f"{clock(int(hours_start * 60))}–{clock(int(hours_end * 60))}"


def build_timetable_pdf(collections: dict, selected_modules: list | None = None, week_start=None) -> bytes:
    week_start = week_start or WEEK_START
    selection = normalise_selection(selected_modules, collections)
    selected_codes = set(selection)
    sessions = [s for s in sessions_from_collections(collections, week_start=week_start)
                if s["code"] in selected_codes or str(s["id"]).startswith("recurring-")]
    catalogue = {m["code"]: m for m in module_catalogue(collections)}

    out = BytesIO()
    page = landscape(A3)
    width, height = page
    pdf = canvas.Canvas(out, pagesize=page)
    pdf.setTitle(f"{TITLE} — {APP_SUBTITLE} — Editable Timetable")
    pdf.setAuthor(APP_NAME)
    pdf.setSubject(f"{TITLE} | {APP_SUBTITLE}")
    pdf.setKeywords("Maternal and Neonatal Health, PhD, academic calendar, timetable, MNH Smart Calendar")

    def banner(subtitle: str) -> float:
        # Repeat the complete programme title and app identity on every exported page.
        pdf.setFillColor(NAVY)
        pdf.rect(0, height - 22 * mm, width, 22 * mm, stroke=0, fill=1)
        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawString(10 * mm, height - 8 * mm, TITLE)
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawRightString(width - 10 * mm, height - 8 * mm, APP_NAME)
        pdf.setFont("Helvetica", 9)
        pdf.drawString(10 * mm, height - 16 * mm, APP_SUBTITLE)
        pdf.drawRightString(width - 10 * mm, height - 16 * mm, subtitle)
        return height - 22 * mm

    def note(text: str, y: float) -> float:
        pdf.setFillColor(colors.HexColor("#33475B"))
        pdf.setFont("Helvetica-Oblique", 10)
        pdf.drawString(10 * mm, y, text)
        return y - 7 * mm

    # ============================ page 1: weekly grid ============================
    top = banner("Weekly Timetable · week commencing " + week_start.strftime("%d %b %Y") + " · type in any cell")
    top = note("This PDF is a fillable form: click a white cell and type. Save the file to keep your edits.", top)
    grid_top = top - 5 * mm
    label_w = 36 * mm
    day_w = (width - 20 * mm - label_w) / 5
    header_h = 12 * mm
    row_h = min((grid_top - header_h - 20 * mm) / len(TIME_SLOTS), 28 * mm)

    # day headers
    for i, name in enumerate(WEEKDAY_NAMES):
        x = 10 * mm + label_w + i * day_w
        pdf.setFillColor(BLUE)
        pdf.rect(x, grid_top - header_h, day_w, header_h, stroke=1, fill=1)
        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawCentredString(x + day_w / 2, grid_top - header_h + 3 * mm,
                              f"{name}  {(week_start + timedelta(days=i)).strftime('%d %b')}")
    # time rows + editable session fields
    form = pdf.acroForm
    y = grid_top - header_h
    for (hs, he) in TIME_SLOTS:
        y -= row_h
        pdf.setFillColor(PALE)
        pdf.rect(10 * mm, y, label_w, row_h, stroke=1, fill=1)
        pdf.setFillColor(NAVY)
        pdf.setFont("Helvetica-Bold", 12)
        label = _slot_label(hs, he)
        pdf.drawCentredString(10 * mm + label_w / 2, y + row_h / 2 - 1 * mm, label)
        if abs(hs - 12) < 0.01:  # lunch row
            pdf.setFillColor(colors.HexColor("#F3E4BD"))
            pdf.setStrokeColor(colors.HexColor("#C9A85D"))
            pdf.rect(10 * mm + label_w, y, 5 * day_w, row_h, stroke=1, fill=1)
            pdf.setFillColor(NAVY)
            pdf.setFont("Helvetica-Bold", 11)
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
                           fontSize=12, value=_ascii(preset), borderWidth=0,
                           fillColor=colors.white, textColor=colors.black,
                           fieldFlags='multiline')
    pdf.showPage()

    # ============================ page 2+: module directory ============================
    # List every available module, not only the selected ones. The fillable checkbox
    # records the export selection, and the assigned lecturer is prefilled from the
    # shared Modules + Facilitators records.
    module_rows = module_catalogue(collections)
    module_rows += [{"code": "", "title": "", "facilitator": ""}] * 3
    week_counts = {}
    for s in sessions:
        week_counts[s["code"]] = week_counts.get(s["code"], 0) + 1
    module_headers = ["Module code", "Module title", "Assigned lecturer", "Sessions this week", "Include"]
    module_x = [10 * mm, 72 * mm, 202 * mm, 300 * mm, 360 * mm]
    module_w = [57 * mm, 125 * mm, 93 * mm, 57 * mm, 50 * mm]
    page_capacity = 12
    for page_start in range(0, len(module_rows), page_capacity):
        if page_start:
            pdf.showPage()
        top = banner("Module Directory · tick the modules included in this export")
        top = note("Module codes, titles and lecturers are editable. Include checkboxes are fillable; save the completed PDF to keep your choices.", top)
        header_h = 11 * mm
        pdf.setFillColor(BLUE)
        pdf.rect(10 * mm, top - header_h, width - 20 * mm, header_h, stroke=1, fill=1)
        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 11)
        for x, label in zip(module_x, module_headers):
            pdf.drawString(x + 1.5 * mm, top - 7.5 * mm, label)
        y = top - header_h
        chunk = module_rows[page_start:page_start + page_capacity]
        for local_idx, module in enumerate(chunk):
            idx = page_start + local_idx
            y -= 16 * mm
            pdf.setStrokeColor(LINE)
            for col in range(5):
                pdf.rect(module_x[col], y, module_w[col], 16 * mm, stroke=1, fill=0)
            for field_name, col, max_chars in (("code", 0, 60), ("title", 1, 120), ("facilitator", 2, 80)):
                form.textfield(name=f"mod_{idx}_{field_name}", tooltip=module_headers[col],
                               x=module_x[col] + 1.5 * mm, y=y + 2 * mm,
                               width=module_w[col] - 3 * mm, height=12 * mm,
                               fontSize=12, value=_ascii(module.get(field_name))[:max_chars],
                               borderWidth=0, fillColor=colors.white, textColor=colors.black)
            code = module.get("code", "")
            pdf.setFillColor(colors.black)
            pdf.setFont("Helvetica-Bold", 11)
            if code:
                pdf.drawCentredString(module_x[3] + module_w[3] / 2, y + 6 * mm,
                                      str(week_counts.get(code, 0)))
            form.checkbox(name=f"mod_{idx}_include", tooltip="Include " + (code or "additional module"),
                           x=module_x[4] + 20 * mm, y=y + 4.5 * mm, size=7 * mm,
                           checked=bool(code and code in selected_codes), buttonStyle="check",
                           borderWidth=1, borderColor=LINE, fillColor=colors.white,
                           textColor=NAVY, forceBorder=True)
    pdf.showPage()

    # ============================ page 3+: session register ============================
    reg_cols = [("Date", 32 * mm), ("Time", 30 * mm), ("Module code", 38 * mm), ("Lecturer", 48 * mm),
                ("Activity / topic", 90 * mm), ("Delivery mode", 34 * mm), ("Status", 30 * mm), ("Notes", 100 * mm)]
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
        pdf.setFont("Helvetica-Bold", 11)
        for cx, cw, (name, _) in zip(reg_x, reg_w, reg_cols):
            pdf.drawString(cx + 1.5 * mm, top - 5.5 * mm, name)
        y = top - 8 * mm
        page_rows = int((y - 18 * mm) // (12 * mm))
        chunk = sessions[i:i + page_rows]
        for r_idx, s in enumerate(chunk):
            y -= 12 * mm
            pdf.setStrokeColor(LINE)
            for cidx in range(len(reg_cols)):
                pdf.rect(reg_x[cidx], y, reg_w[cidx], 12 * mm, stroke=1, fill=0)
            values = [s["date"].strftime("%a %d %b"), f"{s['start']}–{s['end']}", s["code"], s["lecturer"],
                      s["activity"] if s["activity"] != s["code"] else "", s["mode"], s["status"], s["notes"]]
            for cidx, value in enumerate(values):
                form.textfield(name=f"reg_{i + r_idx}_{cidx}", tooltip=reg_cols[cidx][0],
                               x=reg_x[cidx] + 1 * mm, y=y + 1.5 * mm, width=reg_w[cidx] - 2 * mm, height=9 * mm,
                               fontSize=11, value=_ascii(value)[:150], borderWidth=0,
                               fillColor=colors.white, textColor=colors.black)
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
