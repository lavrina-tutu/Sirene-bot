"""Block «Итого» above gantt macro in Confluence storage."""
from __future__ import annotations

import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from mpp_convert import read_csv_rows

ITOGO_LINE1_RE = re.compile(
    r"(Итого:\s*с\s*)(\d{2}\.\d{2}\.\d{2})(\s*по\s*)(\d{2}\.\d{2}\.\d{2})(\s*-\s*)(\d[\d\s]*)(\s*рабочих дней)",
    re.IGNORECASE,
)
ITOGO_LINE2_RE = re.compile(
    r"(Трудозатраты:\s*)(\d[\d\s]*)(\s*человек-часа)",
    re.IGNORECASE,
)


def format_thousands(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def format_date_ddmmyy(dt: str | None) -> str:
    if not dt:
        return "01.01.00"
    s = dt[:10]
    try:
        d = datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        d = datetime.fromisoformat(s.replace("Z", ""))
    return d.strftime("%d.%m.%y")


def compute_itogo_from_csv(tasks_csv: Path, assignments_csv: Path) -> tuple[str, str, int, int]:
    tasks = read_csv_rows(tasks_csv)
    root = next((r for r in tasks if r.get("outline_level") == "1" and r.get("id") != "0"), None)
    if not root:
        raise ValueError("Root task (outline_level=1) not found in tasks CSV")
    d1 = format_date_ddmmyy(root.get("start"))
    d2 = format_date_ddmmyy(root.get("finish"))
    dur = root.get("duration", "0 d").replace(" d", "").strip()
    n_days = math.ceil(float(dur or 0))
    total_work = 0.0
    for a in read_csv_rows(assignments_csv):
        work_raw = (a.get("work") or "0").replace(" h", "").strip()
        try:
            total_work += float(work_raw)
        except ValueError:
            pass
    m_hours = math.ceil(total_work)
    return d1, d2, n_days, m_hours


def compute_itogo_from_gantt(gantt: dict[str, Any]) -> tuple[str, str, int, int]:
    root = gantt["eventsData"][0]
    d1 = format_date_ddmmyy(str(root.get("startDate", ""))[:10])
    d2 = format_date_ddmmyy(str(root.get("endDate", ""))[:10])
    n_days = math.ceil(float(root.get("duration") or 0))

    def leaf_effort(node: dict[str, Any]) -> float:
        if node.get("rollup"):
            return sum(leaf_effort(c) for c in node.get("children", []))
        return float(node.get("effort") or 0)

    m_hours = math.ceil(leaf_effort(root))
    return d1, d2, n_days, m_hours


def build_itogo_html(d1: str, d2: str, n_days: int, m_hours: int) -> str:
    line1 = f"Итого: с {d1} по {d2} - {format_thousands(n_days)} рабочих дней"
    line2 = f"Трудозатраты: {format_thousands(m_hours)} человек-часа"
    return f"<p><strong>{line1}</strong></p><p><strong>{line2}</strong></p>"


def patch_itogo(storage: str, d1: str, d2: str, n_days: int, m_hours: int) -> str:
    n_fmt = format_thousands(n_days)
    m_fmt = format_thousands(m_hours)
    if ITOGO_LINE1_RE.search(storage) and ITOGO_LINE2_RE.search(storage):
        storage = ITOGO_LINE1_RE.sub(
            lambda m: f"{m.group(1)}{d1}{m.group(3)}{d2}{m.group(5)}{n_fmt}{m.group(7)}",
            storage,
            count=1,
        )
        storage = ITOGO_LINE2_RE.sub(
            lambda m: f"{m.group(1)}{m_fmt}{m.group(3)}",
            storage,
            count=1,
        )
        return storage
    return build_itogo_html(d1, d2, n_days, m_hours) + storage


def insert_itogo_above_macro(storage: str, macro_start: int, itogo_html: str) -> str:
    return storage[:macro_start] + itogo_html + storage[macro_start:]


def apply_itogo(storage: str, d1: str, d2: str, n_days: int, m_hours: int, macro_start: int | None = None) -> str:
    if ITOGO_LINE1_RE.search(storage):
        return patch_itogo(storage, d1, d2, n_days, m_hours)
    html = build_itogo_html(d1, d2, n_days, m_hours)
    if macro_start is not None:
        return insert_itogo_above_macro(storage, macro_start, html)
    return html + storage
