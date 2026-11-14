"""Fillable MNH Smart Timetable PDF (ReportLab AcroForm).

The weekly timetable is a single landscape page with Monday-Friday as column
headers and time slots down the left. Module and register pages remain portrait.
All editable entries are real AcroForm fields.
"""
from datetime import timedelta
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from app.services.schedule import WEEK_START, WEEKDAY_NAMES, clock, sessions_from_collections
from app.services.excel_export import module_catalogue, normalise_selection

TITLE = "PhD in Maternal & Neonatal Health"
APP_NAME = "MNH Smart Timetable"
APP_SUBTITLE = "Academic Calendar 2026"

NAVY = colors.HexColor("#102B4E")
PURPLE = colors.HexColor("#45215F")
SILVER = colors.HexColor("#C4CBD4")
GOLD = colors.HexColor("#D4AE55")
PALE = colors.HexColor("#F2F5FA")
PALE_PURPLE = colors.HexColor("#F3EFF7")
LINE = colors.HexColor("#C5D0DE")
INK = colors.HexColor("#17283D")
WHITE = colors.white

TIME_SLOTS = [(8, 10), (10, 12), (12, 13.5), (13, 14), (13.5, 15.5),
              (15.5, 17.5), (17.5, 19), (19, 21)]

_CHAR_MAP = {
    0x2013: "-", 0x2014: "-", 0x2018: "'", 0x2019: "'",
    0x201C: '"', 0x201D: '"', 0x00A0: " ", 0x2026: "...",
}


def _ascii(value) -> str:
    return str(value or "").translate(_CHAR_MAP).encode("latin-1", "replace").decode("latin-1")


def _slot_label(start, end) -> str:
    return f"{clock(int(start * 60))} - {clock(int(end * 60))}"


def build_timetable_pdf(collections: dict, selected_modules: list | None = None, week_start=None, theme: str = "dark") -> bytes:
    theme = theme if theme in {"dark", "white", "violet", "green", "silver"} else "dark"
    palettes = {
        "dark": ("#111318", "#252d38", "#f2c14e", "#cbd5e1", "#1b2028", "#252d38", "#4a5868", "#f8fafc", "#151d27", "#263342", "#3a3425", "#f7d98d"),
        "white": ("#ffffff", "#17427a", "#17427a", "#c6cfda", "#f1f4f8", "#e8eef7", "#c6cfda", "#0a1018", "#ffffff", "#dce6f2", "#e8edf5", "#17427a"),
        "violet": ("#1c1140", "#241548", "#c7b3ff", "#c7b3ff", "#2a1a5c", "#312070", "#5a4a94", "#ffffff", "#312070", "#3a2c70", "#42315e", "#f0e8ff"),
        "green": ("#0a7d3c", "#075f2a", "#ffffff", "#ffffff", "#06612c", "#075f2a", "#a9dcc0", "#ffffff", "#075f2a", "#0a6b34", "#155b35", "#ffffff"),
        "silver": ("#071321", "#0b1b30", "#9dbce0", "#cbd5e1", "#102238", "#132a43", "#405a75", "#f3f6fb", "#132a43", "#1a3450", "#26394f", "#e0eaf7"),
    }
    page_hex, navy_hex, accent_hex, silver_hex, pale_hex, pale_purple_hex, line_hex, ink_hex, field_hex, time_hex, lunch_hex, lunch_text_hex = palettes[theme]
    PAGE = colors.HexColor(page_hex)
    NAVY = colors.HexColor(navy_hex)
    PURPLE = colors.HexColor(accent_hex)
    SILVER = colors.HexColor(silver_hex)
    GOLD = colors.HexColor(accent_hex)
    PALE = colors.HexColor(pale_hex)
    PALE_PURPLE = colors.HexColor(pale_purple_hex)
    LINE = colors.HexColor(line_hex)
    INK = colors.HexColor(ink_hex)
    FIELD = colors.HexColor(field_hex)
    TIME_BG = colors.HexColor(time_hex)
    LUNCH_BG = colors.HexColor(lunch_hex)
    LUNCH_TEXT = colors.HexColor(lunch_text_hex)
    week_start = week_start or WEEK_START
    selection = normalise_selection(selected_modules, collections)
    selected_codes = set(selection)
    sessions = [
        item for item in sessions_from_collections(collections, week_start=week_start)
        if item["code"] in selected_codes or str(item["id"]).startswith("recurring-")
    ]
    module_rows = module_catalogue(collections)

    out = BytesIO()
    width, height = landscape(A4)
    pdf = canvas.Canvas(out, pagesize=landscape(A4))
    pdf.setTitle(f"{APP_NAME} - {TITLE} - Editable Academic Calendar")
    pdf.setAuthor(APP_NAME)
    pdf.setSubject(f"{TITLE} | {APP_SUBTITLE}")
    pdf.setKeywords("MNH, maternal and neonatal health, PhD, editable timetable, academic calendar")

    form = pdf.acroForm
    page_number = 0

    def draw_calendar_icon(x, y, size=11 * mm):
        """Silver vector calendar mark; intentionally not gold."""
        pdf.saveState()
        pdf.setStrokeColor(SILVER)
        pdf.setFillColor(PURPLE)
        pdf.setLineWidth(1.5)
        pdf.roundRect(x, y, size, size * .82, 1.5 * mm, stroke=1, fill=0)
        pdf.line(x, y + size * .58, x + size, y + size * .58)
        pdf.line(x + size * .25, y + size * .92, x + size * .25, y + size * .70)
        pdf.line(x + size * .75, y + size * .92, x + size * .75, y + size * .70)
        for row in range(2):
            for col in range(3):
                cx = x + size * (.24 + col * .26)
                cy = y + size * (.20 + row * .20)
                pdf.circle(cx, cy, .55 * mm, stroke=0, fill=1)
        pdf.restoreState()

    def banner(section: str):
        nonlocal page_number
        page_number += 1
        pdf.setFillColor(PAGE)
        pdf.rect(0, 0, width, height, stroke=0, fill=1)
        pdf.setFillColor(NAVY)
        pdf.rect(0, height - 37 * mm, width, 37 * mm, stroke=0, fill=1)
        draw_calendar_icon(10 * mm, height - 23 * mm, 12 * mm)
        pdf.setFillColor(WHITE)
        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawString(27 * mm, height - 12 * mm, APP_NAME)
        pdf.setFillColor(colors.HexColor("#E8EDF4"))
        pdf.setFont("Helvetica", 8.5)
        pdf.drawString(27 * mm, height - 18 * mm, APP_SUBTITLE)
        # Programme title is deep purple on a pale strip, not gold on navy.
        pdf.setFillColor(PALE_PURPLE)
        pdf.roundRect(10 * mm, height - 33 * mm, width - 20 * mm, 9 * mm, 2 * mm, stroke=0, fill=1)
        pdf.setFillColor(PURPLE)
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(13 * mm, height - 29.8 * mm, TITLE)
        pdf.setFillColor(WHITE)
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawRightString(width - 10 * mm, height - 18 * mm, section)
        return height - 43 * mm

    def footer():
        pdf.setFillColor(GOLD)
        pdf.rect(0, 8 * mm, width, 1.1 * mm, stroke=0, fill=1)
        pdf.setFillColor(INK)
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(10 * mm, 4.5 * mm, "Advancing academic excellence")
        pdf.setFont("Helvetica", 7)
        pdf.drawRightString(width - 10 * mm, 4.5 * mm, f"{APP_NAME}  |  Page {page_number}")

    def section_heading(text, x, y, w):
        pdf.setFillColor(NAVY)
        pdf.roundRect(x, y - 8 * mm, w, 8 * mm, 2 * mm, stroke=0, fill=1)
        pdf.setFillColor(WHITE)
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(x + 3 * mm, y - 5.4 * mm, text)
        return y - 12 * mm

    def field(name, tooltip, x, y, w, h, value="", font_size=16, multiline=False, fill=None):
        # Explicit non-zero /DA font sizes prevent viewers choosing tiny auto-size text.
        flags = "multiline" if multiline else ""
        form.textfield(
            name=name, tooltip=tooltip, x=x, y=y, width=w, height=h,
            fontName="Helvetica", fontSize=font_size, value=_ascii(value)[:1000],
            borderWidth=0, fillColor=fill or FIELD, textColor=INK,
            forceBorder=False, fieldFlags=flags,
        )

    def draw_day_card(day_index, top_y):
        day_name = WEEKDAY_NAMES[day_index]
        day_date = week_start + timedelta(days=day_index)
        x = 10 * mm
        card_w = width - 20 * mm
        row_h = 10.5 * mm
        header_h = 12 * mm
        card_h = header_h + row_h * len(TIME_SLOTS) + 3 * mm
        bottom = top_y - card_h

        pdf.setFillColor(PALE)
        pdf.roundRect(x, bottom, card_w, card_h, 2.5 * mm, stroke=0, fill=1)
        pdf.setFillColor(PURPLE)
        pdf.roundRect(x, top_y - header_h, card_w, header_h, 2 * mm, stroke=0, fill=1)
        pdf.setFillColor(WHITE)
        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawString(x + 4 * mm, top_y - 8 * mm,
                       f"{day_name.upper()}  |  {day_date.strftime('%d %B %Y')}")
        time_w = 43 * mm
        row_top = top_y - header_h
        for slot_index, (start, end) in enumerate(TIME_SLOTS):
            row_y = row_top - (slot_index + 1) * row_h
            is_lunch = abs(start - 12) < 0.01
            bg = LUNCH_BG if is_lunch else (PAGE if slot_index % 2 == 0 else PALE)
            pdf.setFillColor(bg)
            pdf.roundRect(x + 1.5 * mm, row_y + .5 * mm, card_w - 3 * mm, row_h - .8 * mm,
                          1 * mm, stroke=0, fill=1)
            # Dedicated silver time-interval column with strong navy text.
            pdf.setFillColor(TIME_BG)
            pdf.roundRect(x + 1.5 * mm, row_y + .5 * mm, time_w, row_h - .8 * mm,
                          1 * mm, stroke=0, fill=1)
            pdf.setStrokeColor(LINE)
            pdf.setLineWidth(.45)
            pdf.line(x + time_w + 1.5 * mm, row_y + .8 * mm,
                     x + time_w + 1.5 * mm, row_y + row_h - .8 * mm)
            pdf.setFillColor(INK)
            pdf.setFont("Helvetica-Bold", 11)
            pdf.drawCentredString(x + 1.5 * mm + time_w / 2, row_y + 4.1 * mm, _slot_label(start, end))
            if is_lunch:
                pdf.setFillColor(LUNCH_TEXT)
                pdf.setFont("Helvetica-Bold", 11)
                pdf.drawCentredString(x + time_w + (card_w - time_w) / 2, row_y + 4.1 * mm, "Lunch break")
                continue
            matches = [
                item for item in sessions
                if item["weekday"] == day_name
                and item["start_min"] == int(start * 60)
                and item["end_min"] == int(end * 60)
            ]
            preset = ""
            if matches:
                item = matches[0]
                preset = " | ".join(filter(None, [
                    item.get("code"), item.get("lecturer"),
                    item.get("activity") if item.get("activity") != item.get("code") else "",
                ]))
            field(
                f"wk_{day_index}_{int(start * 60)}", f"{day_name} {_slot_label(start, end)}",
                x + time_w + 2 * mm, row_y + 1.0 * mm, card_w - time_w - 6 * mm, row_h - 1.8 * mm,
                preset, font_size=16,
            )
        return bottom - 5 * mm

    # ============================ weekly timetable ============================
    # One landscape weekly grid: weekdays across the top, time slots down the side.
    top = banner("WEEKLY TIMETABLE")
    top = section_heading("Weekly timetable", 10 * mm, top, width - 20 * mm)
    table_x = 10 * mm
    table_w = width - 20 * mm
    time_w = 24 * mm
    day_w = (table_w - time_w) / 5
    header_h = 13 * mm
    row_h = 11.7 * mm
    table_top = top - 3 * mm
    header_bottom = table_top - header_h

    pdf.setFillColor(NAVY)
    pdf.roundRect(table_x, header_bottom, table_w, header_h, 1.5 * mm, stroke=0, fill=1)
    pdf.setFillColor(WHITE)
    pdf.setFont("Helvetica-Bold", 7.5)
    pdf.drawCentredString(table_x + time_w / 2, header_bottom + 5 * mm, "TIME")
    for day_index in range(5):
        day_x = table_x + time_w + day_index * day_w
        day_date = week_start + timedelta(days=day_index)
        pdf.setFillColor(WHITE)
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawCentredString(day_x + day_w / 2, header_bottom + 7.5 * mm,
                              WEEKDAY_NAMES[day_index].upper())
        pdf.setFont("Helvetica", 7)
        pdf.drawCentredString(day_x + day_w / 2, header_bottom + 3.5 * mm,
                              day_date.strftime("%d %b %Y"))
        if day_index:
            pdf.setStrokeColor(LINE)
            pdf.setLineWidth(.35)
            pdf.line(day_x, header_bottom + .8 * mm, day_x, table_top - .8 * mm)

    for slot_index, (start_hour, end_hour) in enumerate(TIME_SLOTS):
        row_top = header_bottom - slot_index * row_h
        row_y = row_top - row_h
        is_lunch = abs(start_hour - 12) < .01
        row_bg = LUNCH_BG if is_lunch else (PAGE if slot_index % 2 == 0 else PALE)
        pdf.setFillColor(row_bg)
        pdf.rect(table_x, row_y, table_w, row_h, stroke=0, fill=1)
        pdf.setFillColor(TIME_BG)
        pdf.rect(table_x, row_y, time_w, row_h, stroke=0, fill=1)
        pdf.setStrokeColor(LINE)
        pdf.setLineWidth(.4)
        pdf.rect(table_x, row_y, table_w, row_h, stroke=1, fill=0)
        pdf.line(table_x + time_w, row_y, table_x + time_w, row_top)
        pdf.setFillColor(NAVY)
        pdf.setFont("Helvetica-Bold", 7.2)
        pdf.drawCentredString(table_x + time_w / 2, row_y + 4.5 * mm,
                              _slot_label(start_hour, end_hour))

        if is_lunch:
            pdf.setFillColor(LUNCH_TEXT)
            pdf.setFont("Helvetica-Bold", 9)
            pdf.drawCentredString(table_x + time_w + (table_w - time_w) / 2,
                                  row_y + 4.5 * mm, "LUNCH BREAK")
            continue

        for day_index in range(5):
            cell_x = table_x + time_w + day_index * day_w
            if day_index:
                pdf.setStrokeColor(LINE)
                pdf.line(cell_x, row_y, cell_x, row_top)
            day_name = WEEKDAY_NAMES[day_index]
            matches = [
                item for item in sessions
                if item["weekday"] == day_name
                and item["start_min"] == int(start_hour * 60)
                and item["end_min"] == int(end_hour * 60)
            ]
            preset = ""
            if matches:
                item = matches[0]
                preset = " | ".join(filter(None, [
                    item.get("code"), item.get("lecturer"),
                    item.get("activity") if item.get("activity") != item.get("code") else "",
                ]))
            field(
                f"wk_{day_index}_{int(start_hour * 60)}",
                f"{day_name} {_slot_label(start_hour, end_hour)}",
                cell_x + 1 * mm, row_y + 1.5 * mm,
                day_w - 2 * mm, row_h - 3 * mm,
                preset, font_size=10,
            )

    footer()
    pdf.showPage()

    # The supporting module and register pages retain their portrait layout.
    pdf.setPageSize(A4)
    width, height = A4

    # ============================ module directory ============================
    counts = {}
    for item in sessions:
        counts[item["code"]] = counts.get(item["code"], 0) + 1
    module_rows = list(module_rows) + [{"code": "", "title": "", "facilitator": ""}] * 2
    page_capacity = 5
    for start_idx in range(0, len(module_rows), page_capacity):
        top = banner("MODULE DIRECTORY")
        top = section_heading("Modules and facilitators", 10 * mm, top, width - 20 * mm)
        top -= 2 * mm
        chunk = module_rows[start_idx:start_idx + page_capacity]
        for local_idx, module in enumerate(chunk):
            idx = start_idx + local_idx
            card_h = 39 * mm
            bottom = top - card_h
            pdf.setFillColor(PALE)
            pdf.roundRect(10 * mm, bottom, width - 20 * mm, card_h - 2 * mm, 2 * mm, stroke=0, fill=1)
            pdf.setFillColor(PURPLE)
            pdf.setFont("Helvetica-Bold", 8)
            pdf.drawString(14 * mm, top - 6 * mm, "MODULE CODE")
            pdf.drawString(76 * mm, top - 6 * mm, "SESSIONS")
            pdf.setFillColor(INK)
            pdf.setFont("Helvetica-Bold", 9)
            pdf.drawString(14 * mm, top - 11 * mm, str(counts.get(module.get("code", ""), 0)))
            field(f"mod_{idx}_code", "Module code", 14 * mm, top - 19 * mm, 55 * mm, 7 * mm,
                  module.get("code", ""), font_size=16, fill=FIELD)
            field(f"mod_{idx}_title", "Module title", 73 * mm, top - 19 * mm, 112 * mm, 7 * mm,
                  module.get("title", ""), font_size=16, fill=FIELD)
            field(f"mod_{idx}_facilitator", "Assigned lecturer", 14 * mm, top - 32 * mm,
                  171 * mm, 8 * mm, module.get("facilitator", ""), font_size=16, fill=FIELD)
            form.checkbox(
                name=f"mod_{idx}_include", tooltip="Include " + (module.get("code") or "additional module"),
                x=width - 24 * mm, y=top - 10 * mm, size=5 * mm,
                checked=bool(module.get("code") and module.get("code") in selected_codes),
                buttonStyle="check", borderWidth=1, borderColor=LINE,
                fillColor=FIELD, textColor=PURPLE, forceBorder=True,
            )
            top = bottom - 4 * mm
        footer()
        pdf.showPage()

    # ============================ session register ============================
    # Vertical editable cards keep every register field readable on phone screens.
    register_rows = sessions
    register_capacity = 3
    if not register_rows:
        register_chunks = [[]]
    else:
        register_chunks = [
            register_rows[i:i + register_capacity]
            for i in range(0, len(register_rows), register_capacity)
        ]
    for page_idx, chunk in enumerate(register_chunks):
        top = banner("SESSION REGISTER")
        top = section_heading("Session register  |  editable records", 10 * mm, top, width - 20 * mm)
        top -= 2 * mm
        for local_idx, item in enumerate(chunk):
            idx = page_idx * register_capacity + local_idx
            card_h = 58 * mm
            bottom = top - card_h
            pdf.setFillColor(PALE)
            pdf.roundRect(10 * mm, bottom, width - 20 * mm, card_h - 2 * mm, 2 * mm, stroke=0, fill=1)
            pdf.setFillColor(PURPLE)
            pdf.setFont("Helvetica-Bold", 8)
            pdf.drawString(14 * mm, top - 6 * mm, f"SESSION {idx + 1}")

            def register_field(field_key, label, value, x_mm, y_mm, width_mm):
                pdf.setFillColor(PURPLE)
                pdf.setFont("Helvetica-Bold", 7)
                pdf.drawString(x_mm * mm, y_mm * mm + 8.5 * mm, label.upper())
                field(
                    f"reg_{idx}_{field_key}", label,
                    x_mm * mm, y_mm * mm, width_mm * mm, 7.5 * mm,
                    value, font_size=16,
                )

            register_field(
                "date_time", "Date / time",
                f"{item['date'].strftime('%a %d %b')}  {item['start']}-{item['end']}",
                14, (top / mm) - 19, 88,
            )
            register_field("module_code", "Module code", item.get("code", ""),
                           110, (top / mm) - 19, 75)
            register_field(
                "activity", "Activity / topic",
                item.get("activity") if item.get("activity") != item.get("code") else "",
                14, (top / mm) - 31, 171,
            )
            register_field("lecturer", "Lecturer", item.get("lecturer", ""),
                           14, (top / mm) - 43, 88)
            register_field(
                "mode_status", "Delivery mode / status",
                f"{item.get('mode', '')} / {item.get('status', '')}",
                110, (top / mm) - 43, 75,
            )
            register_field("notes", "Notes", item.get("notes", ""),
                           14, (top / mm) - 55, 171)
            top = bottom - 4 * mm
        if not chunk:
            pdf.setFillColor(INK)
            pdf.setFont("Helvetica", 10)
            pdf.drawString(12 * mm, top - 8 * mm, "No sessions are currently scheduled for this week.")
        footer()
        if page_idx < len(register_chunks) - 1:
            pdf.showPage()

    pdf.save()
    return out.getvalue()


__all__ = ["build_timetable_pdf"]
