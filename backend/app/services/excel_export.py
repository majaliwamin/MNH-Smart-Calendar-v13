"""Editable Excel timetable (.xlsx) built from the stored collections. Pure function: no web framework."""
from io import BytesIO
from datetime import timedelta
from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from app.services.schedule import (LUNCH_END, LUNCH_START, WEEK_START, WEEKDAY_NAMES, clock,
                                   overlaps_lunch, sessions_from_collections)

TITLE = "PhD in Maternal and Neonatal Health : 3rd Block"
NAVY, BLUE, PALE, WHITE = "102B4E", "1F497D", "EAF1F8", "FFFFFF"
GRID = "9DB2C8"
LUNCH_FILL = "F6E7C1"

COLUMNS = 6  # Time + Monday to Friday

# The three programme modules every export must be able to include (the web app
# defines the same defaults in the browser; they are repeated here so exports
# work even before the module list has been saved to the shared database).
DEFAULT_MODULES = [
    {"code": "ARMN – 8100", "title": "Antimicrobial Resistance in Maternal & Neonatal Health", "facilitator": "G Bandawe"},
    {"code": "MIPN 8100", "title": "Medical Imaging in Pregnancy and Neonates", "facilitator": "Not specified"},
    {"code": "PNIM-8100", "title": "Pregnancy and Neonatal Immunology", "facilitator": "D Mzinza"},
]


def module_catalogue(collections: dict) -> list:
    """All known modules (defaults first), each {code,title,facilitator} — the selection list."""
    stored = collections.get("modules", {}) or {}
    by_code = {}
    for item_id, data in stored.items():
        code = str(data.get("code") or item_id).strip()
        if code:
            by_code[code] = {"code": code, "title": str(data.get("title") or ""), "facilitator": str(data.get("facilitator") or "")}
    for default in DEFAULT_MODULES:
        by_code.setdefault(default["code"], dict(default))
    return sorted(by_code.values(), key=lambda m: m["code"].lower())


def normalise_selection(selected: list | None, collections: dict) -> list:
    """Chosen module codes, defaulting to the three programme modules; unknown codes dropped."""
    catalogue = {m["code"]: m for m in module_catalogue(collections)}
    if not selected:
        return [m["code"] for m in DEFAULT_MODULES]
    out = []
    for code in selected:
        code = str(code).strip()
        if code in catalogue and code not in out:
            out.append(code)
    return out


def build_timetable_workbook(collections: dict, selected_modules: list | None = None) -> bytes:
    sessions = sessions_from_collections(collections)
    selection = normalise_selection(selected_modules, collections)
    thin = Side(style="thin", color=GRID)
    box = Border(left=thin, right=thin, top=thin, bottom=thin)

    wb = Workbook()
    ws = wb.active
    ws.title = "Weekly Timetable"
    details = wb.create_sheet("Session Details")
    directory = wb.create_sheet("Module Directory")
    readme = wb.create_sheet("Read Me")

    # ---- Header band: merged across the full width of the table ---------------
    last_col = get_column_letter(COLUMNS)
    ws.merge_cells(f"A1:{last_col}1")
    ws["A1"] = f"{TITLE} — Weekly Timetable"
    ws["A1"].font = Font(size=15, bold=True, color=WHITE)
    ws["A1"].fill = PatternFill("solid", fgColor=NAVY)
    ws["A1"].alignment = Alignment(vertical="center", horizontal="left", indent=1)
    ws.row_dimensions[1].height = 30

    ws.merge_cells(f"A2:{last_col}2")
    ws["A2"] = "Week commencing Monday, 9 November 2026 · Monday to Friday"
    ws["A2"].font = Font(italic=True, size=11, color="33475B")
    ws["A2"].fill = PatternFill("solid", fgColor=PALE)
    ws["A2"].alignment = Alignment(vertical="center", horizontal="left", indent=1)
    ws.row_dimensions[2].height = 20

    # ---- Day header row: one ordinary cell per day ---------------------------
    headers = ["Time"] + [f"{name}\n{(WEEK_START + timedelta(days=i)).strftime('%d %b %Y')}"
                          for i, name in enumerate(WEEKDAY_NAMES)]
    for col, text in enumerate(headers, start=1):
        c = ws.cell(3, col, text)
        c.font = Font(bold=True, size=12, color=WHITE)
        c.fill = PatternFill("solid", fgColor=BLUE)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = box
    ws.row_dimensions[3].height = 40

    # ---- Session Details (the editable register) ------------------------------
    detail_headers = ["Record ID", "Date", "Weekday", "Start time", "End time", "Module code", "Module title",
                      "Lecturer", "Activity", "Delivery mode", "Session status", "Notes"]
    details.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(detail_headers))
    details["A1"] = "SESSION REGISTER — editable copy"
    details["A1"].font = Font(size=15, bold=True, color=WHITE)
    details["A1"].fill = PatternFill("solid", fgColor=NAVY)
    details.row_dimensions[1].height = 28
    for col, text in enumerate(detail_headers, start=1):
        c = details.cell(2, col, text)
        c.font = Font(bold=True, color=WHITE)
        c.fill = PatternFill("solid", fgColor=BLUE)
        c.alignment = Alignment(wrap_text=True, vertical="center")
        c.border = box
    details.row_dimensions[2].height = 30
    details.freeze_panes = "A3"

    # ---- Body: one plain row per interval, lunch kept as its own row ----------
    intervals = sorted({(s["start_min"], s["end_min"]) for s in sessions})
    plan = [("session", iv) for iv in intervals]
    index = next((i for i, (_, iv) in enumerate(plan) if iv[0] >= LUNCH_START), len(plan))
    plan.insert(index, ("lunch", (LUNCH_START, LUNCH_END)))

    weekly_cell_for = {}
    row = 4
    for kind, (start, end) in plan:
        time_cell = ws.cell(row, 1)
        time_cell.border = box
        time_cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        time_cell.font = Font(bold=True, size=11, color=NAVY)
        time_cell.fill = PatternFill("solid", fgColor=PALE)
        if kind == "lunch":
            time_cell.value = f"{clock(start)}\nLunch Break"
            for col in range(2, COLUMNS + 1):
                cell = ws.cell(row, col)
                cell.value = None
                cell.border = box
                cell.fill = PatternFill("solid", fgColor=LUNCH_FILL)
                cell.alignment = Alignment(horizontal="center", vertical="center")
            ws.row_dimensions[row].height = 30
        else:
            time_cell.value = f"{clock(start)}–{clock(end)}"
            for col, name in enumerate(WEEKDAY_NAMES, start=2):
                cell = ws.cell(row, col)
                cell.border = box
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                match = [s for s in sessions
                         if s["weekday"] == name and (s["start_min"], s["end_min"]) == (start, end)]
                if match:
                    s = match[0]
                    weekly_cell_for[s["id"]] = cell.coordinate
                    cell.value = "\n".join(filter(None, [
                        s["code"],
                        s["module_title"] if s["module_title"] != s["code"] else "",
                        s["activity"] if s["activity"] not in (s["code"], s["module_title"]) else "",
                        s["lecturer"],
                    ]))
                    cell.font = Font(bold=True, size=11, color=NAVY)
                    cell.fill = PatternFill("solid", fgColor="DCE8F5")
                    cell.comment = Comment(
                        f"{s['start']}–{s['end']} · {s['mode']}\nLecturer: {s['lecturer'] or 'not assigned'}",
                        "MNH Calendar")
            ws.row_dimensions[row].height = 64
        row += 1

    for number, s in enumerate(sessions, start=3):
        values = [s["id"], s["date"], s["weekday"], s["start"], s["end"], s["code"], s["module_title"],
                  s["lecturer"], s["activity"], s["mode"], s["status"], s["notes"]]
        for col, value in enumerate(values, start=1):
            c = details.cell(number, col, value)
            c.alignment = Alignment(vertical="top", wrap_text=True)
            c.border = box
        details.cell(number, 2).number_format = "ddd, dd mmm yyyy"
        target = weekly_cell_for.get(s["id"])
        if target:
            details.cell(number, 1).hyperlink = f"#'Weekly Timetable'!{target}"
            details.cell(number, 1).font = Font(color="0563C1", underline="single")
            details.cell(number, 1).alignment = Alignment(vertical="top", wrap_text=True)

    link = ws.cell(2, 1)
    link.value = f"{ws['A2'].value}          →  Session Details"
    link.hyperlink = "#'Session Details'!A3"
    link.font = Font(italic=True, size=11, color="0563C1", underline="single")
    link.alignment = Alignment(vertical="center", horizontal="left", indent=1)

    details.auto_filter.ref = f"A2:L{max(3, len(sessions) + 2)}"
    for col, width in enumerate([24, 17, 13, 11, 11, 18, 40, 24, 32, 16, 16, 38], start=1):
        details.column_dimensions[get_column_letter(col)].width = width

    ws.column_dimensions["A"].width = 18
    for col in range(2, COLUMNS + 1):
        ws.column_dimensions[get_column_letter(col)].width = 28
    ws.freeze_panes = "B4"

    # A normal spreadsheet: gridlines on, print titles repeat the header band.
    ws.sheet_view.showGridLines = True
    details.sheet_view.showGridLines = True
    ws.print_title_rows = "1:3"
    ws.page_setup.orientation = "landscape"
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0

    # ---- Module Directory: the selected modules, editable ----------------------
    dir_headers = ["Module code", "Module title", "Facilitator", "Included in this export", "Sessions this week"]
    directory.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(dir_headers))
    directory["A1"] = "MODULE DIRECTORY — edit freely; add rows for extra modules"
    directory["A1"].font = Font(size=15, bold=True, color=WHITE)
    directory["A1"].fill = PatternFill("solid", fgColor=NAVY)
    directory.row_dimensions[1].height = 28
    for col, text in enumerate(dir_headers, start=1):
        c = directory.cell(2, col, text)
        c.font = Font(bold=True, color=WHITE)
        c.fill = PatternFill("solid", fgColor=BLUE)
        c.alignment = Alignment(wrap_text=True, vertical="center")
        c.border = box
    directory.row_dimensions[2].height = 26
    catalogue = {m["code"]: m for m in module_catalogue(collections)}
    week_counts = {}
    for s in sessions:
        week_counts[s["code"]] = week_counts.get(s["code"], 0) + 1
    for row_num, code in enumerate(selection, start=3):
        module = catalogue.get(code, {"code": code, "title": "", "facilitator": ""})
        values = [module["code"], module["title"], module["facilitator"], "Yes", week_counts.get(code, 0)]
        for col, value in enumerate(values, start=1):
            c = directory.cell(row_num, col, value)
            c.alignment = Alignment(vertical="top", wrap_text=True)
            c.border = box
    # three blank editable rows so users can add modules directly in the file
    for row_num in range(len(selection) + 3, len(selection) + 6):
        for col in range(1, len(dir_headers) + 1):
            directory.cell(row_num, col).border = box
    for col, width in enumerate([18, 46, 22, 22, 16], start=1):
        directory.column_dimensions[get_column_letter(col)].width = width
    directory.sheet_view.showGridLines = True

    notes = [TITLE + " — Excel timetable",
             "Weekly Timetable: Monday to Friday only, one row per time interval. Lunch Break (12:00–13:30) has its own row.",
             "Header rows 1–2 are merged across the full width; every cell below is an ordinary editable cell.",
             "Session Details: use the filter arrows to filter by date, module, lecturer, delivery mode or status; click a Record ID to jump to that cell.",
             "Module Directory: the modules chosen at export time; every cell is editable and blank rows are provided for extra modules.",
             "This workbook is an independent copy. Editing it does not change the live calendar database."]
    for i, text in enumerate(notes, start=1):
        c = readme.cell(i, 1, text)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        readme.row_dimensions[i].height = 32 if i > 1 else 30
    readme["A1"].font = Font(size=15, bold=True, color=WHITE)
    readme["A1"].fill = PatternFill("solid", fgColor=NAVY)
    readme.column_dimensions["A"].width = 120
    readme.sheet_view.showGridLines = False

    out = BytesIO()
    wb.save(out)
    return out.getvalue()


__all__ = ["build_timetable_workbook", "module_catalogue", "normalise_selection", "overlaps_lunch"]
