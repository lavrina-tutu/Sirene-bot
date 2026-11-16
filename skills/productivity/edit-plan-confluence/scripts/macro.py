"""Parse and build gantt-chart-planner macro in Confluence storage."""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass


_MACRO_TAG = re.compile(r"</?ac:structured-macro\b[^>]*>", re.DOTALL)
_ATTR = re.compile(r"([\w:-]+)\s*=\s*([\"'])(.*?)\2", re.DOTALL)


@dataclass
class MacroInfo:
    macro_id: str
    param_id: str
    param_hash: str
    attachment_name: str
    _span: tuple[int, int] | None = None

    @property
    def span(self) -> tuple[int, int] | None:
        return self._span


def find_macros(storage: str) -> list[MacroInfo]:
    """Enumerate every target, including nested macros; malformed targets fail closed."""
    from xml.etree import ElementTree as ET
    from html import unescape

    stack = []
    targets = []
    for match in _MACRO_TAG.finditer(storage):
        tag = match.group()
        if tag.startswith("</"):
            if not stack:
                raise ValueError("unbalanced structured-macro")
            start, attrs = stack.pop()
            if attrs.get("ac:name") != "gantt-chart-planner":
                continue
            fragment = storage[start:match.end()]
            try:
                root = ET.fromstring('<root xmlns:ac="urn:ac" xmlns:ri="urn:ri">' + fragment + '</root>')[0]
                params = {}
                for child in root:
                    if child.tag == "{urn:ac}parameter":
                        key = child.get("{urn:ac}name")
                        if key in params:
                            raise ValueError("duplicate Gantt parameter")
                        params[key] = child.text or ""
                mid = attrs.get("ac:macro-id")
                pid, phash = params.get("id"), params.get("hash")
                if not all((mid, pid, phash)):
                    raise ValueError("incomplete Gantt macro identifiers")
            except ET.ParseError as exc:
                raise ValueError("malformed Gantt macro") from exc
            targets.append(MacroInfo(mid, pid, phash, f"gantt-chart-{pid}.json", (start, match.end())))
        else:
            attrs = {k: unescape(v) for k, _, v in _ATTR.findall(tag)}
            if tag.endswith("/>"):
                if attrs.get("ac:name") == "gantt-chart-planner":
                    raise ValueError("incomplete self-closing Gantt macro")
                continue
            stack.append((match.start(), attrs))
    if stack:
        raise ValueError("unclosed structured-macro")
    return sorted(targets, key=lambda target: target.span[0])


def find_macro(storage: str) -> MacroInfo | None:
    targets = find_macros(storage)
    if len(targets) > 1:
        raise ValueError(f"ambiguous Gantt target: {len(targets)} macros")
    return targets[0] if targets else None


def macro_span(storage: str) -> tuple[int, int] | None:
    target = find_macro(storage)
    return target.span if target else None


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
