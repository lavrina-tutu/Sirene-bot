"""
Шаблон: конвертация MPP CSV → xlsx по структуре Google Sheets шаблона.

Использование:
  1. Распарси .mpp через read_mpp.py — получишь __tasks.csv, __resources.csv, __assignments.csv
  2. Прочитай заголовки шаблона GS:
       curl -sL "https://docs.google.com/spreadsheets/d/<ID>/export?format=csv&gid=0" | head -1
  3. Подстрой HEADERS и маппинг под реальные колонки шаблона
  4. Запусти скрипт

Колонки шаблона GS (типичный вариант для русского MS Project):
  №, Название задачи, Длительность, Названия ресурсов, Текст1, Начало, Окончание, Предшественники
"""
import csv
import re
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment
from openpyxl.utils import get_column_letter

# venv: /home/tkachenkoav/hermes-agent/.venv (openpyxl уже установлен)

DAYS_RU = {0: "пн", 1: "вт", 2: "ср", 3: "чт", 4: "пт", 5: "сб", 6: "вс"}

TASKS_CSV = "/tmp/ml_plan__tasks.csv"
ASSIGNMENTS_CSV = "/tmp/ml_plan__assignments.csv"
OUTPUT_XLSX = "/tmp/output_по_шаблону.xlsx"

# Заголовки — копируй из шаблона GS
HEADERS = ["No", "Название задачи", "Длительность", "Названия ресурсов",
           "Текст1", "Начало", "Окончание", "Предшественники"]


def fmt_date(iso_str):
    """ISO datetime → 'чт 04.06.26' (формат шаблона GS)"""
    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_str)
        return DAYS_RU[dt.weekday()] + " " + dt.strftime("%d.%m.%y")
    except Exception:
        return iso_str


def fmt_dur(dur_str):
    """'9.0 d' → '9 дней'"""
    if not dur_str:
        return ""
    m = re.match(r"([\d.]+)\s*d", str(dur_str))
    if m:
        d = float(m.group(1))
        n = int(d) if d == int(d) else d
        return str(n) + " дней"
    return dur_str


def main():
    tasks = []
    with open(TASKS_CSV, encoding="utf-8") as f:
        tasks = list(csv.DictReader(f))

    assign_map = {}
    with open(ASSIGNMENTS_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            tid = row.get("task_id", "")
            rname = row.get("resource_name", "")
            if tid and rname:
                assign_map.setdefault(tid, []).append(rname)

    wb = Workbook()
    ws = wb.active
    ws.title = "Задачи"
    ws.append(HEADERS)

    # Стиль заголовка — тёмно-синий как стандарт GS
    hfill = PatternFill("solid", fgColor="1F4E79")
    hfont = Font(bold=True, color="FFFFFF", size=10)
    for cell in ws[1]:
        cell.fill = hfill
        cell.font = hfont
        cell.alignment = Alignment(horizontal="center", vertical="center")

    task_num = 0
    for t in tasks:
        tid = t.get("id", "")
        if tid == "0":   # корневая задача-заглушка
            continue
        task_num += 1
        preds_raw = t.get("predecessors", "")
        preds_clean = preds_raw.replace("[", "").replace("]", "").replace(" ", "")
        ws.append([
            task_num,
            t.get("name", ""),
            fmt_dur(t.get("duration", "")),
            "; ".join(assign_map.get(str(tid), [])),
            t.get("notes", ""),
            fmt_date(t.get("start", "")),
            fmt_date(t.get("finish", "")),
            preds_clean,
        ])

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = "A1:" + get_column_letter(len(HEADERS)) + "1"

    col_widths = [5, 60, 12, 25, 40, 14, 14, 15]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    for row in ws.iter_rows(min_row=2):
        row[1].alignment = Alignment(wrap_text=True, vertical="top")
        row[4].alignment = Alignment(wrap_text=True, vertical="top")

    wb.save(OUTPUT_XLSX)
    print("Saved: " + OUTPUT_XLSX + " (" + str(task_num) + " задач)")


if __name__ == "__main__":
    main()
