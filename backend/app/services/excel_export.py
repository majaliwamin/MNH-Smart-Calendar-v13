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
LUNCH_FILL = "F6E7C1"


def build_timetable_workbook(collections: dict) -> bytes:
    sessions = sessions_from_collections(collections)
    thin = Side(style="thin", color="8FA3BA")
    box = Border(left=thin, right=thin, top=thin, bottom=thin)

    wb = Workbook()
    ws = wb.active
    ws.title = "Weekly Timetable"
    details = wb.create_sheet("Session Details")
    readme = wb.create_sheet("Read Me")

    # ---- Weekly Timetable header ------------------------------------------------
    ws.merge_cells("A1:F1")
    ws["A1"] = f"{TITLE} — Weekly Timetable"
    ws["A1"].font = Font(size=16, bold=True, color=WHITE)
    ws["A1"].fill = PatternFill("solid", fgColor=NAVY)
    ws["A1"].alignment = Alignment(vertical="center", indent=1)
    ws.row_dimensions[1].height = 32
    ws.merge_cells("A2:E2")
    ws["A2"] = "Week commencing Monday, 9 November 2026 · Monday to Friday"
    ws["A2"].font = Font(italic=True, color="52657A")
    ws.append([])  # keep row 3 free for the header row written below
    headers = ["Time"] + [f"{name}\n{(WEEK_START + timedelta(days=i)).strftime('%d %b %Y')}" for i, name in enumerate(WEEKDAY_NAMES)]
    for col, text in enumerate(headers, start=1):
        c = ws.cell(3, col, text)
        c.font = Font(bold=True, color=WHITE)
        c.fill = PatternFill("solid", fgColor=BLUE)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = box
    ws.row_dimensions[3].height = 36

    # ---- Session Details (the editable register) --------------------------------
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

    # ---- Row plan: one row per distinct interval, lunch inserted at 12:00 -----------
    intervals = sorted({(s["start_min"], s["end_min"]) for s in sessions})
    plan = [("session", iv) for iv in intervals]
    index = next((i for i, (_, iv) in enumerate(plan) if iv[0] >= LUNCH_START), len(plan))
    plan.insert(index, ("lunch", (LUNCH_START, LUNCH_END)))

    weekly_cell_for = {}
    row = 4
    for kind, (start, end) in plan:
        label = f"{clock(start)}–{clock(end)}"
        time_cell = ws.cell(row, 1, label)
        time_cell.font = Font(bold=True, color=NAVY)
        time_cell.fill = PatternFill("solid", fgColor=PALE)
        time_cell.alignment = Alignment(horizontal="center", vertical="center")
        time_cell.border = box
        if kind == "lunch":
            ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=6)
            lunch = ws.cell(row, 2, "L u n c h   B r e a k")
            lunch.font = Font(bold=True, size=12, color="6B4A12")
            lunch.alignment = Alignment(horizontal="center", vertical="center")
            for col in range(2, 7):
                ws.cell(row, col).fill = PatternFill("solid", fgColor=LUNCH_FILL)
                ws.cell(row, col).border = box
            ws.row_dimensions[row].height = 27      # about half of a normal 54-point row
        else:
            for col, name in enumerate(WEEKDAY_NAMES, start=2):
                cell = ws.cell(row, col)
                cell.border = box
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                match = [s for s in sessions if s["weekday"] == name and (s["start_min"], s["end_min"]) == (start, end)]
                if match:
                    s = match[0]
                    weekly_cell_for[s["id"]] = cell.coordinate
                    cell.value = "\n".join(filter(None, [s["code"], s["module_title"] if s["module_title"] != s["code"] else "",
                                                          s["activity"] if s["activity"] not in (s["code"], s["module_title"]) else "",
                                                          s["lecturer"]]))
                    cell.font = Font(bold=True, color=NAVY)
                    cell.fill = PatternFill("solid", fgColor="DCE8F5")
                    cell.comment = Comment(f"{s['start']}–{s['end']} · {s['mode']}\nLecturer: {s['lecturer'] or 'not assigned'}", "MNH Calendar")
            ws.row_dimensions[row].height = 72
        row += 1
    last_row = row - 1

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
    link = ws.cell(2, 6, "Open Session Details ›")
    link.hyperlink = "#'Session Details'!A3"
    link.font = Font(color="0563C1", underline="single")
    link.alignment = Alignment(horizontal="right")
    details.auto_filter.ref = f"A2:L{max(3, len(sessions) + 2)}"
    for col, width in enumerate([24, 17, 13, 11, 11, 18, 40, 24, 32, 16, 16, 38], start=1):
        details.column_dimensions[get_column_letter(col)].width = width

    ws.column_dimensions["A"].width = 16
    for col in range(2, 7):
        ws.column_dimensions[get_column_letter(col)].width = 30
    ws.freeze_panes = "B4"
    ws.sheet_view.showGridLines = False
    details.sheet_view.showGridLines = False
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.print_title_rows = "1:3"

    notes = [TITLE + " — Excel timetable",
             "Weekly Timetable: Monday to Friday only. Use 'Open Session Details' (top right) to see every record; in Session Details click a Record ID to jump to that session's cell.",
             "Session Details: use the filter arrows to filter by date, module, lecturer, delivery mode or status.",
             "Lunch Break (12:00–13:30) is shown as a merged half-height row. Sessions that overlap it keep their own row.",
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


__all__ = ["build_timetable_workbook", "overlaps_lunch"]
