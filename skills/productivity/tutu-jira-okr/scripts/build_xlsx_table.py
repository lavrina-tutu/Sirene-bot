"""
Generic Excel table builder for Jira-derived reports (OKR/SR tables meant for
copy-paste into Confluence, or to send as a standalone file).

Usage pattern (adapt columns/data/hyperlinks per task):

    python3 build_xlsx_table.py

Or import build_table() from execute_code and call it directly with your data.

Design notes:
- Any column that should link to a Jira issue gets cell.hyperlink + blue/underline font.
- Every cell wraps text and gets a thin border; header row is bold on light-blue fill.
- Column widths and row heights are set generously for multi-line cell content.
- Save under WorkVault/Projects/<okr-tool|sr-tool>/<person or shared>/..., then rclone sync.
"""
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

JIRA_BASE = "https://hq.tutu.ru/browse/"


def build_table(path, headers, rows, hyperlink_cols=None, col_widths=None, sheet_title="Sheet1"):
    """
    headers: list[str] — column headers
    rows: list[dict] — each dict has keys: 'cells' (list[str], same length as headers)
                        and optionally 'links' (dict: col_index -> jira_key) for that row
    hyperlink_cols: unused if per-row 'links' given; kept for simple uniform cases
    col_widths: list[int] matching headers, or None for defaults
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_title

    ws.append(headers)

    header_fill = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
    thin = Side(style="thin", color="999999")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = border

    for row in rows:
        cells = row["cells"]
        ws.append(cells)
        r = ws.max_row
        links = row.get("links", {})
        for col_idx, jira_key in links.items():
            cell = ws.cell(row=r, column=col_idx + 1)  # 1-indexed
            cell.hyperlink = JIRA_BASE + jira_key
            cell.font = Font(color="0563C1", underline="single")

    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        for cell in row:
            if cell.alignment.wrap_text is None or not cell.alignment.wrap_text:
                cell.alignment = Alignment(wrap_text=True, vertical="top")
            cell.border = border

    widths = col_widths or [40] * len(headers)
    for i, w in enumerate(widths):
        ws.column_dimensions[chr(65 + i)].width = w

    for i in range(2, ws.max_row + 1):
        ws.row_dimensions[i].height = 45

    wb.save(path)
    return path


if __name__ == "__main__":
    # Example: 2-column table with Jira-linked first column
    example_rows = [
        {"cells": ["Пример задачи 1", "Иванов И."], "links": {0: "OKRS-0000"}},
        {"cells": ["Пример задачи 2", "Петров П."], "links": {0: "OKRS-0001"}},
    ]
    build_table(
        "/tmp/example.xlsx",
        headers=["Наименование", "Исполнитель"],
        rows=example_rows,
        col_widths=[60, 25],
    )
    print("Example written to /tmp/example.xlsx")
