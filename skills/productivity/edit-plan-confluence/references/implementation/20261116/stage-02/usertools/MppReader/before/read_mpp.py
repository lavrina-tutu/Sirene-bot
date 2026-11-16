#!/usr/bin/env python3
"""
Чтение файлов Microsoft Project (.mpp / .mpx / .xml / MSPDI) через mpxj
(JPype + Java). Поддерживается также XER (Primavera) и ряд других форматов.

Использование:
    read_mpp.py <путь_к_файлу> [--format json|csv|both] [--out-dir DIR] [--summary]

JSON печатается в stdout, CSV-файлы (tasks/resources/assignments) сохраняются
рядом с исходным файлом (или в --out-dir).
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


def _start_jvm() -> None:
    import mpxj  # noqa: F401  — регистрирует JAR-ы в classpath JPype
    import jpype
    import jpype.imports  # noqa: F401
    if not jpype.isJVMStarted():
        jpype.startJVM()


def _to_str(x) -> str:
    return "" if x is None else str(x)


def _fmt_date(d) -> str | None:
    if d is None:
        return None
    try:
        return d.toString()
    except Exception:
        return str(d)


def _fmt_dur(dur) -> str | None:
    if dur is None:
        return None
    try:
        return f"{float(dur.getDuration())} {dur.getUnits().toString()}"
    except Exception:
        return str(dur)


def _collect_background_colors(project) -> dict[int, str]:
    """Возвращает {task_unique_id: "#RRGGBB"} — фон строки задачи в таблице
    Gantt-вью MS Project. Берётся из ColumnFontStyle.getBackgroundColor() для
    всех GanttChartView; на задачу выбирается самый частый ненулевой цвет
    среди её ячеек (исключая чистый белый #FFFFFF — это артефакт стилей без
    явной заливки фона).
    """
    from collections import Counter
    per_task: dict[int, Counter] = {}
    try:
        views = list(project.getViews() or [])
    except Exception:
        return {}
    for v in views:
        try:
            cls_name = v.getClass().getName()
        except Exception:
            continue
        if "GanttChartView" not in cls_name:
            continue
        try:
            tfs = v.getTableFontStyles()
        except Exception:
            tfs = None
        if not tfs:
            continue
        for s in list(tfs):
            try:
                uid = s.getRowUniqueID()
                bg = s.getBackgroundColor()
            except Exception:
                continue
            if uid is None or bg is None:
                continue
            try:
                rgb = (int(bg.getRed()), int(bg.getGreen()), int(bg.getBlue()))
            except Exception:
                continue
            if rgb == (255, 255, 255):
                continue  # пустой стиль без явной заливки
            per_task.setdefault(int(uid), Counter())[rgb] += 1
    out: dict[int, str] = {}
    for uid, c in per_task.items():
        rgb = c.most_common(1)[0][0]
        out[uid] = "#{:02X}{:02X}{:02X}".format(*rgb)
    return out


def read_project(path: str) -> dict[str, Any]:
    _start_jvm()
    from org.mpxj.reader import UniversalProjectReader
    from org.mpxj import TaskField

    reader = UniversalProjectReader()
    project = reader.read(path)
    if project is None:
        raise RuntimeError(f"Не удалось прочитать файл: {path}")

    bg_colors = _collect_background_colors(project)

    props = project.getProjectProperties()
    project_info = {
        "name": _to_str(props.getProjectTitle()),
        "author": _to_str(props.getAuthor()),
        "company": _to_str(props.getCompany()),
        "start_date": _fmt_date(props.getStartDate()),
        "finish_date": _fmt_date(props.getFinishDate()),
        "status_date": _fmt_date(props.getStatusDate()),
        "default_calendar": _to_str(props.getDefaultCalendar().getName()) if props.getDefaultCalendar() else "",
    }

    # Задачи
    tasks = []
    for t in project.getTasks():
        if t is None:
            continue
        try:
            preds = []
            rels = t.getPredecessors()
            if rels:
                for r in rels:
                    src = r.getPredecessorTask() if hasattr(r, "getPredecessorTask") else r.getSourceTask()
                    if src is not None and src.getID() is not None:
                        preds.append(int(src.getID()))
            uid_val = int(t.getUniqueID()) if t.getUniqueID() is not None else None
            tasks.append({
                "id": int(t.getID()) if t.getID() is not None else None,
                "uid": uid_val,
                "wbs": _to_str(t.getWBS()),
                "outline_level": int(t.getOutlineLevel() or 0),
                "name": _to_str(t.getName()),
                "duration": _fmt_dur(t.getDuration()),
                "start": _fmt_date(t.getStart()),
                "finish": _fmt_date(t.getFinish()),
                "percent_complete": float(t.getPercentageComplete() or 0),
                "milestone": bool(t.getMilestone()),
                "summary": bool(t.getSummary()),
                "predecessors": preds,
                "notes": _to_str(t.getNotes())[:500],
                "text1": _to_str(t.get(TaskField.valueOf("TEXT1")))[:500],
                "text2": _to_str(t.get(TaskField.valueOf("TEXT2")))[:500],
                "text3": _to_str(t.get(TaskField.valueOf("TEXT3")))[:500],
                "text4": _to_str(t.get(TaskField.valueOf("TEXT4")))[:500],
                "text5": _to_str(t.get(TaskField.valueOf("TEXT5")))[:500],
                "text6": _to_str(t.get(TaskField.valueOf("TEXT6")))[:500],
                "background_color": bg_colors.get(uid_val) if uid_val is not None else None,
            })
        except Exception as e:  # noqa: BLE001
            tasks.append({"error": str(e), "id": None})

    # Ресурсы
    resources = []
    for r in project.getResources():
        if r is None:
            continue
        try:
            resources.append({
                "id": int(r.getID()) if r.getID() is not None else None,
                "uid": int(r.getUniqueID()) if r.getUniqueID() is not None else None,
                "name": _to_str(r.getName()),
                "type": _to_str(r.getType().toString()) if r.getType() else "",
                "email": _to_str(r.getEmailAddress()),
                "group": _to_str(r.getGroup()),
                "max_units": float(r.getMaxUnits() or 0),
            })
        except Exception as e:  # noqa: BLE001
            resources.append({"error": str(e)})

    # Назначения
    assignments = []
    for a in project.getResourceAssignments():
        if a is None:
            continue
        try:
            task = a.getTask()
            res = a.getResource()
            assignments.append({
                "task_id": int(task.getID()) if task and task.getID() is not None else None,
                "task_name": _to_str(task.getName()) if task else "",
                "resource_id": int(res.getID()) if res and res.getID() is not None else None,
                "resource_name": _to_str(res.getName()) if res else "",
                "units": float(a.getUnits() or 0),
                "work": _fmt_dur(a.getWork()),
                "start": _fmt_date(a.getStart()),
                "finish": _fmt_date(a.getFinish()),
            })
        except Exception as e:  # noqa: BLE001
            assignments.append({"error": str(e)})

    return {
        "project": project_info,
        "stats": {
            "task_count": len(tasks),
            "resource_count": len(resources),
            "assignment_count": len(assignments),
        },
        "tasks": tasks,
        "resources": resources,
        "assignments": assignments,
    }


def write_csv(data: dict[str, Any], out_dir: Path, stem: str) -> list[Path]:
    written: list[Path] = []
    for key in ("tasks", "resources", "assignments"):
        rows = data.get(key) or []
        if not rows:
            continue
        all_keys: list[str] = []
        seen: set[str] = set()
        for row in rows:
            for k in row.keys():
                if k not in seen:
                    seen.add(k)
                    all_keys.append(k)
        path = out_dir / f"{stem}__{key}.csv"
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=all_keys)
            w.writeheader()
            for row in rows:
                w.writerow({k: ("" if row.get(k) is None else row.get(k)) for k in all_keys})
        written.append(path)
    return written


def main() -> int:
    ap = argparse.ArgumentParser(description="Чтение MS Project (.mpp/.mpx/.xml) через mpxj")
    ap.add_argument("path", help="Путь к .mpp/.mpx/.xml/.xer файлу")
    ap.add_argument("--format", choices=("json", "csv", "both"), default="both")
    ap.add_argument("--out-dir", default=None,
                    help="Куда складывать CSV (по умолчанию — рядом с файлом)")
    ap.add_argument("--summary", action="store_true",
                    help="В JSON оставить только сводку + первые 20 задач")
    args = ap.parse_args()

    src = Path(args.path).expanduser().resolve()
    if not src.is_file():
        print(f"ERROR: файл не найден: {src}", file=sys.stderr)
        return 2

    data = read_project(str(src))

    out_dir = Path(args.out_dir).expanduser().resolve() if args.out_dir else src.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = src.stem

    csv_paths: list[Path] = []
    if args.format in ("csv", "both"):
        csv_paths = write_csv(data, out_dir, stem)

    if args.format in ("json", "both"):
        payload: dict[str, Any] = {
            "source": str(src),
            "project": data["project"],
            "stats": data["stats"],
            "csv_files": [str(p) for p in csv_paths],
        }
        if args.summary:
            payload["tasks_preview"] = data["tasks"][:20]
        else:
            payload["tasks"] = data["tasks"]
            payload["resources"] = data["resources"]
            payload["assignments"] = data["assignments"]
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))

    return 0


if __name__ == "__main__":
    sys.exit(main())
