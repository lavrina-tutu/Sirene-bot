"""Parse and build gantt-chart-planner macro in Confluence storage."""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass


MACRO_RE = re.compile(
    r'<ac:structured-macro[^>]*ac:name="gantt-chart-planner"[^>]*ac:macro-id="([^"]+)"[^>]*>'
    r'.*?<ac:parameter ac:name="id">([^<]+)</ac:parameter>'
    r'.*?<ac:parameter ac:name="hash">([^<]+)</ac:parameter>',
    re.DOTALL,
)


@dataclass
class MacroInfo:
    macro_id: str
    param_id: str
    param_hash: str
    attachment_name: str

    @property
    def span(self) -> tuple[int, int] | None:
        return None


def find_macro(storage: str) -> MacroInfo | None:
    m = MACRO_RE.search(storage)
    if not m:
        return None
    macro_id = m.group(1)
    param_id = m.group(2)
    return MacroInfo(
        macro_id=macro_id,
        param_id=param_id,
        param_hash=m.group(3),
        # 📌 Имя вложения плагин gantt-chart-planner строит от ac:parameter "id",
        # НЕ от ac:macro-id (проверено на живой AB 519492935: вложение gantt-chart-<param_id>.json).
        attachment_name=f"gantt-chart-{param_id}.json",
    )


def macro_span(storage: str) -> tuple[int, int] | None:
    m = MACRO_RE.search(storage)
    if not m:
        return None
    return m.start(), m.end()


def build_macro_html(macro_id: str, param_id: str, param_hash: str) -> str:
    return (
        f'<p><ac:structured-macro ac:name="gantt-chart-planner" ac:schema-version="1" '
        f'ac:macro-id="{macro_id}">'
        f'<ac:parameter ac:name="id">{param_id}</ac:parameter>'
        f'<ac:parameter ac:name="hash">{param_hash}</ac:parameter>'
        f"</ac:structured-macro></p>"
    )


def new_macro_ids() -> tuple[str, str, str]:
    macro_id = str(uuid.uuid4())
    param_id = uuid.uuid4().hex
    param_hash = uuid.uuid4().hex
    return macro_id, param_id, param_hash


def insert_macro(storage: str, macro_html: str, before_macro: str = "") -> str:
    if before_macro:
        return before_macro + macro_html + storage
    return macro_html + storage
