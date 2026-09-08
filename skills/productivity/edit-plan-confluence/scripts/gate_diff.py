"""Gate diff text before Confluence writes."""
from __future__ import annotations

from typing import Any

from env import page_url
from itogo import build_itogo_html, compute_itogo_from_gantt
from mpp_convert import count_tasks


CONFIRM_WORDS = frozenset({"лей", "пиши", "да"})


def is_confirmed(text: str) -> bool:
    return text.strip().lower() in CONFIRM_WORDS


def format_itogo_pair(d1: str, d2: str, n: int, m: int) -> str:
    return build_itogo_html(d1, d2, n, m).replace("<p><strong>", "").replace("</strong></p>", "\n")


def build_diff(
    *,
    page_id: str | int,
    title: str,
    operation: str,
    gantt: dict[str, Any] | None = None,
    had_existing_plan: bool = False,
    child_title: str | None = None,
    warnings: list[str] | None = None,
    empty_plan: bool = False,
    itogo_before: str | None = None,
    itogo_after: str | None = None,
    itogo_values: tuple[str, str, int, int] | None = None,
) -> str:
    lines = [
        f"pageId: {page_id}",
        f"title: {title}",
        f"URL: {page_url(page_id)}",
        f"операция: {operation}",
    ]
    if child_title:
        lines.append(f"дочка title: {child_title}")
    if gantt:
        root = gantt["eventsData"][0]
        if itogo_values:
            d1, d2, n, m = itogo_values
        else:
            d1, d2, n, m = compute_itogo_from_gantt(gantt)
        lines.append(f"задач: {count_tasks(root)}")
        lines.append(f"корень: {str(root.get('startDate', ''))[:10]} — {str(root.get('endDate', ''))[:10]}")
        lines.append(f"Итого: {d1} — {d2}, {n} р.д., {m} ч-ч")
    if empty_plan:
        lines.append("⚠ план пустой (шаблон без задач)")
    if had_existing_plan:
        lines.append("⚠ план будет заменён целиком; правки не из этого MPP сгорят")
    if itogo_before and itogo_after:
        lines.append(f"Итого было:\n{itogo_before}")
        lines.append(f"Итого станет:\n{itogo_after}")
    for w in warnings or []:
        lines.append(f"⚠ {w}")
    lines.append("")
    lines.append('Подтверди «лей» / «пиши» / «да» для записи.')
    return "\n".join(lines)
