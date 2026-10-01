"""Block «Итого» above gantt macro in Confluence storage."""
from __future__ import annotations

import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from macro import macro_span
from mpp_convert import read_csv_rows

ITOGO_LINE1_RE = re.compile(
    r"(Итого:\s*с\s*)(\d{2}\.\d{2}\.\d{2})(\s*по\s*)(\d{2}\.\d{2}\.\d{2})(\s*-\s*)(\d[\d\s]*)(\s*рабочих дней)",
    re.IGNORECASE,
)
_TRUDOZATRATY_CORE = (
    r"Трудозатраты:\s*\d[\d\s\xa0]*\s*"
    r"(?:человеко?-часов?|человек-часа|человек-часов|человеко-часов)"
)
ITOGO_LINE2_RE = re.compile(
    rf"(?:<p>(?:<strong>)?{_TRUDOZATRATY_CORE}(?:</strong>)?</p>|{_TRUDOZATRATY_CORE})",
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
    return (
        f"<p><strong>Итого: с {d1} по {d2} - {format_thousands(n_days)} рабочих дней</strong></p>"
    )


def strip_trudozatraty(storage: str) -> str:
    """Удалить абзац/текст «Трудозатраты: …» целиком. Идемпотентно."""
    prev = None
    out = storage
    while out != prev:
        prev = out
        out = ITOGO_LINE2_RE.sub("", out)
    return out


def patch_itogo(storage: str, d1: str, d2: str, n_days: int, m_hours: int) -> str:
    storage = strip_trudozatraty(storage)
    n_fmt = format_thousands(n_days)
    if ITOGO_LINE1_RE.search(storage):
        storage = ITOGO_LINE1_RE.sub(
            lambda m: f"{m.group(1)}{d1}{m.group(3)}{d2}{m.group(5)}{n_fmt}{m.group(7)}",
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
    storage = strip_trudozatraty(storage)
    html = build_itogo_html(d1, d2, n_days, m_hours)
    if macro_start is not None:
        span = macro_span(storage)
        start = span[0] if span is not None else macro_start
        return insert_itogo_above_macro(storage, start, html)
    return html + storage
