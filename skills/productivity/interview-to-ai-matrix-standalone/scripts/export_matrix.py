#!/usr/bin/env python3
"""Export AI-Зация matrix to CSV or XLSX from a JSON spec.

Рендер-слой навыка interview-to-ai-matrix-standalone. Вся логика анализа — на
стороне агента/consensus_matrix.py; этот скрипт только превращает spec.json в
файлы с цветовой разметкой по легенде и маркировкой критических стадий.

Usage:
    python export_matrix.py --input spec.json --format xlsx --output matrix.xlsx
    python export_matrix.py --input spec.json --format csv  --output-dir ./out/
    python export_matrix.py --input spec.json --format both --output matrix.xlsx --output-dir ./out/

Требует openpyxl для XLSX:
    pip install openpyxl
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path


def load_spec(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def slugify(name: str) -> str:
    """Имя файла = имя процесса. Сохраняем кириллицу, пунктуацию → дефис."""
    s = (name or "matrix").strip().lower()
    s = re.sub(
        r"[\s\u00a0\u2013\u2014\u2212/\\:;,.!?\"'`()\[\]{}<>|@#$%^&*+=~]+",
        "-",
        s,
    )
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "matrix"


def _stage_label(stage: dict, with_duration: bool = True) -> str:
    name = stage["name"]
    label = f"⚠️ КРИТИЧЕСКОЕ: {name}" if stage.get("critical") else name
    if with_duration and stage.get("duration"):
        label += f" ({stage['duration']})"
    return label


def write_csv(spec: dict, out_dir: str) -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    process = slugify(spec.get("process_name"))
    stages = spec["stages"]
    stage_headers = [_stage_label(s) for s in stages]
    activities = spec["activities"]
    written: list[Path] = []

    for kind, label in (("as_is", "AS_IS"), ("to_be", "TO_BE")):
        path = out / f"{process}_{label}.csv"
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["Когнитивная деятельность \\ Стадии", *stage_headers])
            for activity in activities:
                cells = spec.get(kind, {}).get(activity, {})
                row = [activity] + [cells.get(s["name"], "Нет") for s in stages]
                w.writerow(row)
        written.append(path)
        print(f"[csv] wrote {path}")
    return written


def _classify(cell: str | None) -> str | None:
    if not cell:
        return "no"
    c = cell.strip().lower()
    if c in {"нет", "—", "-"}:
        return "no"
    if "ассистентский" in c:
        return "assist"
    if "агентный" in c:
        return "agent"
    if "сотрудничеств" in c:
        return "human_collab"
    return None


def write_xlsx(spec: dict, out_path: str) -> Path:
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
        from openpyxl.utils import get_column_letter
    except ImportError:
        sys.exit("openpyxl is required. Install: pip install openpyxl")

    wb = Workbook()
    wb.remove(wb.active)

    fills = {
        "assist":         PatternFill("solid", fgColor="D5E8D4"),
        "agent":          PatternFill("solid", fgColor="FFE6CC"),
        "human_collab":   PatternFill("solid", fgColor="DAE8FC"),
        "no":             PatternFill("solid", fgColor="F5F5F5"),
        "critical":       PatternFill("solid", fgColor="C00000"),
        "critical_light": PatternFill("solid", fgColor="FFCCCC"),
        "header":         PatternFill("solid", fgColor="404040"),
    }
    thin = Side(border_style="thin", color="999999")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    wrap_top = Alignment(wrap_text=True, vertical="top")
    wrap_center = Alignment(wrap_text=True, vertical="top", horizontal="center")

    def add_context_sheet() -> None:
        ws = wb.create_sheet("Контекст")
        status = spec.get("status") or (
            "Рекомендация — итоговые назначения «человек / AI-агент / AI + ревью» "
            "требуют обсуждения с владельцем процесса и стейкхолдерами перед запуском работ."
        )
        info = [
            ("Процесс",            spec.get("process_name", "")),
            ("Владелец",           spec.get("owner", "")),
            ("Цель",               spec.get("purpose", "")),
            ("Частота",            spec.get("frequency", "")),
            ("KPI",                spec.get("kpi", "")),
            ("Дата формирования",  spec.get("date", "")),
            ("Версия",             spec.get("version", "")),
            ("Статус матрицы",     status),
        ]
        repro = spec.get("reproducibility")
        if isinstance(repro, dict):
            info.append((
                "Воспроизводимость",
                f"Прогонов: {repro.get('runs', '?')}; "
                f"стабильность AS IS: {repro.get('stability_as_is', '?')}; "
                f"стабильность TO BE: {repro.get('stability_to_be', '?')}; "
                f"консенсус: мажоритарное голосование по типам AI.",
            ))
        for i, (k, v) in enumerate(info, start=1):
            kc = ws.cell(row=i, column=1, value=k)
            kc.font = Font(bold=True)
            kc.alignment = wrap_top
            ws.cell(row=i, column=2, value=v).alignment = wrap_top
        ws.column_dimensions["A"].width = 22
        ws.column_dimensions["B"].width = 90

    def add_legend_sheet() -> None:
        ws = wb.create_sheet("Легенда")
        rows = [
            ("■", "Ассистентский AI",
             "Автоматизация рутинных задач, помощь в поиске информации, подготовка отчётов, документирование.",
             "assist"),
            ("■", "Агентный AI",
             "Выполнение сложных аналитических задач, моделирование, паттерн-распознавание, сценарный анализ.",
             "agent"),
            ("■", "Сотрудничество с человеком",
             "Интерактивная работа (аналитические платформы, дискуссии), требуется критическое мышление человека.",
             "human_collab"),
            ("—", "Нет применимости",
             "Требуется высокая креативность, критическое суждение, человеческая интуиция.",
             "no"),
            ("⚠️", "КРИТИЧЕСКОЕ",
             "Самые трудозатратные / блокирующие стадии.",
             "critical_light"),
        ]
        for j, h in enumerate(["Маркер", "Тип", "Описание"], start=1):
            c = ws.cell(row=1, column=j, value=h)
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = fills["header"]
            c.alignment = wrap_top
        for i, (m, t, d, fkey) in enumerate(rows, start=2):
            ws.cell(row=i, column=1, value=m).alignment = wrap_center
            tc = ws.cell(row=i, column=2, value=t)
            tc.alignment = wrap_top
            if fkey:
                tc.fill = fills[fkey]
            ws.cell(row=i, column=3, value=d).alignment = wrap_top
        ws.column_dimensions["A"].width = 10
        ws.column_dimensions["B"].width = 34
        ws.column_dimensions["C"].width = 80

    def add_matrix_sheet(title: str, cells_data: dict) -> None:
        ws = wb.create_sheet(title)
        stages = spec["stages"]
        activities = spec["activities"]

        hc = ws.cell(row=1, column=1, value="Когнитивная деятельность \\ Стадии")
        hc.font = Font(bold=True, color="FFFFFF")
        hc.fill = fills["header"]
        hc.alignment = wrap_center
        hc.border = border

        for j, stage in enumerate(stages, start=2):
            name = stage["name"]
            label = f"⚠️ КРИТИЧЕСКОЕ:\n{name}" if stage.get("critical") else name
            if stage.get("duration"):
                label += f"\n({stage['duration']})"
            c = ws.cell(row=1, column=j, value=label)
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = fills["critical"] if stage.get("critical") else fills["header"]
            c.alignment = wrap_center
            c.border = border

        for i, activity in enumerate(activities, start=2):
            ac = ws.cell(row=i, column=1, value=activity)
            ac.font = Font(bold=True)
            ac.alignment = wrap_top
            ac.border = border
            act_cells = cells_data.get(activity, {})
            for j, stage in enumerate(stages, start=2):
                val = act_cells.get(stage["name"], "Нет")
                cc = ws.cell(row=i, column=j, value=val)
                cc.alignment = wrap_top
                cc.border = border
                kind = _classify(val)
                if kind in fills:
                    cc.fill = fills[kind]

        ws.column_dimensions[get_column_letter(1)].width = 34
        for j in range(2, len(stages) + 2):
            ws.column_dimensions[get_column_letter(j)].width = 40
        ws.row_dimensions[1].height = 70
        for i in range(2, len(activities) + 2):
            ws.row_dimensions[i].height = 130
        ws.freeze_panes = "B2"

    def add_stage_summary_sheet() -> None:
        items = spec.get("stage_summary") or []
        if not items:
            return
        ws = wb.create_sheet("Сводка по стадиям")
        headers = ["#", "Стадия", "Ответственный в TO BE", "Комментарий"]
        for j, h in enumerate(headers, start=1):
            c = ws.cell(row=1, column=j, value=h)
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = fills["header"]
            c.alignment = wrap_center
        for i, item in enumerate(items, start=2):
            ws.cell(row=i, column=1, value=i - 1).alignment = wrap_top
            ws.cell(row=i, column=2, value=item.get("stage", "")).alignment = wrap_top
            rc = ws.cell(row=i, column=3, value=item.get("responsible", ""))
            rc.alignment = wrap_top
            resp = (item.get("responsible") or "").lower()
            if "ai-агент" in resp and "ревью" not in resp:
                rc.fill = fills["agent"]
            elif "ревью" in resp:
                rc.fill = fills["assist"]
            elif "человек" in resp:
                rc.fill = fills["no"]
            ws.cell(row=i, column=4, value=item.get("comment", "")).alignment = wrap_top
        ws.column_dimensions["A"].width = 5
        ws.column_dimensions["B"].width = 40
        ws.column_dimensions["C"].width = 26
        ws.column_dimensions["D"].width = 70

    def add_human_only_sheet() -> None:
        items = spec.get("human_only") or []
        if not items:
            return
        ws = wb.create_sheet("Что не отдаём ИИ")
        headers = ["Этап процесса", "Что не отдаём ИИ", "Почему"]
        for j, h in enumerate(headers, start=1):
            c = ws.cell(row=1, column=j, value=h)
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = fills["header"]
            c.alignment = wrap_center
        for i, item in enumerate(items, start=2):
            stage = item.get("stage") or item.get("where", "")
            what  = item.get("what")  or item.get("decision", "")
            why   = item.get("why", "")
            ws.cell(row=i, column=1, value=stage).alignment = wrap_top
            ws.cell(row=i, column=2, value=what).alignment  = wrap_top
            ws.cell(row=i, column=3, value=why).alignment   = wrap_top
        ws.column_dimensions["A"].width = 36
        ws.column_dimensions["B"].width = 50
        ws.column_dimensions["C"].width = 60

    def add_cjm_sheet() -> None:
        """Лист CJM: путь клиента в табличном виде, состояния AS IS → TO BE."""
        items = spec.get("cjm") or []
        if not items:
            return

        ws = wb.create_sheet("CJM (AS IS → TO BE)")

        headers = [
            "#",
            "Этап пути клиента",
            "Действия клиента",
            "Точки контакта",
            "AS IS — опыт сейчас",
            "TO BE — опыт с ИИ",
            "Эффект / улучшение",
        ]
        for j, h in enumerate(headers, start=1):
            c = ws.cell(row=1, column=j, value=h)
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = fills["header"]
            c.alignment = wrap_center
            c.border = border

        for i, item in enumerate(items, start=2):
            stage = item.get("stage", "")
            critical = item.get("critical")
            label = f"⚠️ КРИТИЧЕСКОЕ: {stage}" if critical else stage
            ws.cell(row=i, column=1, value=i - 1).alignment = wrap_center
            sc = ws.cell(row=i, column=2, value=label)
            sc.alignment = wrap_top
            if critical:
                sc.fill = fills["critical_light"]
            ws.cell(row=i, column=3, value=item.get("actions", "")).alignment = wrap_top
            ws.cell(row=i, column=4, value=item.get("touchpoints", "")).alignment = wrap_top
            ai = ws.cell(row=i, column=5, value=item.get("as_is", ""))
            ai.alignment = wrap_top
            ai.fill = fills["no"]
            tb = ws.cell(row=i, column=6, value=item.get("to_be", ""))
            tb.alignment = wrap_top
            tb.fill = fills["assist"]
            ws.cell(row=i, column=7, value=item.get("effect", "")).alignment = wrap_top
            for j in range(1, 8):
                ws.cell(row=i, column=j).border = border

        ws.column_dimensions["A"].width = 5
        ws.column_dimensions["B"].width = 26
        ws.column_dimensions["C"].width = 34
        ws.column_dimensions["D"].width = 26
        ws.column_dimensions["E"].width = 44
        ws.column_dimensions["F"].width = 44
        ws.column_dimensions["G"].width = 34
        ws.row_dimensions[1].height = 36
        for i in range(2, len(items) + 2):
            ws.row_dimensions[i].height = 90
        ws.freeze_panes = "A2"

    def add_effect_sheet() -> None:
        """Лист: ожидаемый эффект от внедрения ИИ (по стадиям)."""
        stages = spec.get("stages") or []
        stage_summary_map = {
            item["stage"]: item
            for item in (spec.get("stage_summary") or [])
            if "stage" in item
        }
        rows = []
        for stage in stages:
            name = stage.get("name", "")
            rows.append({
                "role":        stage.get("actor", ""),
                "task":        name,
                "as_is":       stage.get("as_is_short", ""),
                "to_be":       stage.get("to_be_short", ""),
                "savings":     stage.get("time_savings") or "—",
                "executor":    stage_summary_map.get(name, {}).get("responsible", ""),
            })
        has_data = any(r["as_is"] or r["to_be"] or r["savings"] != "—" for r in rows)
        if not has_data:
            return

        ws = wb.create_sheet("Эффект от внедрения")

        title_cell = ws.cell(row=1, column=1,
                             value="ОЖИДАЕМЫЙ ЭФФЕКТ ОТ ВНЕДРЕНИЯ ИИ")
        title_cell.font = Font(bold=True, size=12, color="FFFFFF")
        title_cell.fill = fills["header"]
        title_cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=6)

        headers = [
            "Роль",
            "Процесс / задача",
            "AS IS",
            "TO BE с агентом",
            "Экономия времени",
            "Кто выполняет (TO BE)",
        ]
        for j, h in enumerate(headers, start=1):
            c = ws.cell(row=2, column=j, value=h)
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = fills["header"]
            c.alignment = wrap_center
            c.border = border

        executor_fills = {
            "ai-агент":         fills["agent"],
            "ревью":            fills["assist"],
            "человек":          fills["no"],
        }

        for i, row in enumerate(rows, start=3):
            ws.cell(row=i, column=1, value=row["role"]).alignment = wrap_top
            ws.cell(row=i, column=2, value=row["task"]).alignment = wrap_top
            ws.cell(row=i, column=3, value=row["as_is"]).alignment = wrap_top
            ws.cell(row=i, column=4, value=row["to_be"]).alignment = wrap_top
            ws.cell(row=i, column=5, value=row["savings"]).alignment = wrap_center
            ec = ws.cell(row=i, column=6, value=row["executor"])
            ec.alignment = wrap_top
            resp_lower = row["executor"].lower()
            for kw, fill in executor_fills.items():
                if kw in resp_lower:
                    ec.fill = fill
                    break
            for j in range(1, 7):
                ws.cell(row=i, column=j).border = border

        ws.column_dimensions["A"].width = 18
        ws.column_dimensions["B"].width = 34
        ws.column_dimensions["C"].width = 40
        ws.column_dimensions["D"].width = 46
        ws.column_dimensions["E"].width = 22
        ws.column_dimensions["F"].width = 30
        ws.row_dimensions[1].height = 28
        ws.row_dimensions[2].height = 36
        for i in range(3, len(rows) + 3):
            ws.row_dimensions[i].height = 70
        ws.freeze_panes = "A3"

    add_context_sheet()
    add_legend_sheet()
    add_matrix_sheet("AS IS", spec.get("as_is", {}))
    add_matrix_sheet("TO BE", spec.get("to_be", {}))
    add_stage_summary_sheet()
    add_human_only_sheet()
    add_cjm_sheet()
    add_effect_sheet()

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    print(f"[xlsx] wrote {out}")
    return out


def main() -> None:
    p = argparse.ArgumentParser(description="Export AI-Зация matrix to CSV / XLSX")
    p.add_argument("--input", required=True, help="JSON spec file")
    p.add_argument("--format", choices=["csv", "xlsx", "both"], default="xlsx")
    p.add_argument("--output", help="Output XLSX file (when --format xlsx|both)")
    p.add_argument("--output-dir", help="Output dir for CSV (when --format csv|both)")
    args = p.parse_args()

    spec = load_spec(args.input)

    if args.format in ("csv", "both"):
        write_csv(spec, args.output_dir or ".")
    if args.format in ("xlsx", "both"):
        out = args.output or f"{slugify(spec.get('process_name'))}.xlsx"
        write_xlsx(spec, out)


if __name__ == "__main__":
    main()
