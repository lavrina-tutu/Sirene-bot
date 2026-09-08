"""Orchestration: preview / apply MPP plan to Confluence gantt page."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from child_page import create_child_page, default_child_title
from conf_client import ConfluenceClient
from env import page_url
from gantt_attachment import find_gantt_attachment, load_gantt_json, upload_gantt_json
from gate_diff import build_diff, is_confirmed
from itogo import apply_itogo, build_itogo_html, compute_itogo_from_csv, compute_itogo_from_gantt
from macro import build_macro_html, find_macro, macro_span, new_macro_ids
from mpp_calendar import calendar_from_mpp
from mpp_convert import copy_parent_gantt, convert_mpp_csv, empty_gantt
from mpp_input import export_csv

SKILL_ROOT = Path(__file__).resolve().parents[1]
EMPTY_TEMPLATE = SKILL_ROOT / "references" / "empty-gantt-template.json"
LIVE_AB_PAGE = "519492935"
TEST_PAGE = "519501810"


@dataclass
class PreviewResult:
    page_id: str
    title: str
    macro_id: str | None
    attachment_version: int | None
    diff_text: str


@dataclass
class ApplyResult:
    page_id: str
    title: str
    page_url: str
    attachment_version: int
    itogo_html: str


def _load_empty_template() -> dict[str, Any]:
    return json.loads(EMPTY_TEMPLATE.read_text(encoding="utf-8"))


def _guard_page(page_id: str, allow_live_ab: bool) -> None:
    if page_id == LIVE_AB_PAGE and not allow_live_ab:
        raise PermissionError(
            f"pageId {LIVE_AB_PAGE} — живая AB; только с --allow-live-ab и явной командой"
        )


def build_plan_from_mpp(
    mpp_path: Path,
    existing_gantt: dict[str, Any] | None = None,
) -> dict[str, Any]:
    csvs = export_csv(mpp_path)
    template = existing_gantt or _load_empty_template()
    calendars = calendar_from_mpp(csvs.mpp_path)
    return convert_mpp_csv(
        csvs.tasks_csv,
        csvs.resources_csv,
        csvs.assignments_csv,
        template_json=template,
        calendars_data=calendars,
    )


def build_plan_copy_parent(parent_gantt: dict[str, Any]) -> dict[str, Any]:
    return copy_parent_gantt(parent_gantt)


def build_plan_empty(title: str | None = None) -> dict[str, Any]:
    return empty_gantt(title)


def preview_page(client: ConfluenceClient, page_id: str, allow_live_ab: bool = False) -> PreviewResult:
    _guard_page(page_id, allow_live_ab)
    page = client.get_page(page_id)
    storage = page["body"]["storage"]["value"]
    macro = find_macro(storage)
    att_ver = None
    macro_id = macro.macro_id if macro else None
    if macro:
        attachments = client.list_attachments(page_id)
        att = find_gantt_attachment(attachments, macro)
        if att:
            att_ver = att.version
    diff = build_diff(
        page_id=page_id,
        title=page["title"],
        operation="preview (read-only)",
    )
    return PreviewResult(page_id, page["title"], macro_id, att_ver, diff)


def prepare_apply_diff(
    client: ConfluenceClient,
    page_id: str,
    mpp_path: Path | None,
    *,
    allow_live_ab: bool = False,
) -> tuple[dict, dict[str, Any], str, list[str]]:
    _guard_page(page_id, allow_live_ab)
    page = client.get_page(page_id)
    storage = page["body"]["storage"]["value"]
    macro = find_macro(storage)
    warnings: list[str] = []
    existing_gantt: dict[str, Any] | None = None
    had_plan = False
    if macro:
        existing_gantt, _att = load_gantt_json(client, page_id, macro)
        had_plan = bool(existing_gantt)

    if mpp_path:
        gantt = build_plan_from_mpp(mpp_path, existing_gantt if existing_gantt else None)
        csvs = export_csv(mpp_path)
        d1, d2, n, m = compute_itogo_from_csv(csvs.tasks_csv, csvs.assignments_csv)
    else:
        raise ValueError("MPP file required for apply")

    itogo_after = build_itogo_html(d1, d2, n, m)
    diff = build_diff(
        page_id=page_id,
        title=page["title"],
        operation="замена JSON вложения + патч «Итого»",
        gantt=gantt,
        had_existing_plan=had_plan,
        itogo_values=(d1, d2, n, m),
        itogo_after=itogo_after.replace("<p><strong>", "").replace("</strong></p>", "\n"),
        warnings=warnings,
    )
    return page, gantt, diff, warnings


def apply_plan(
    client: ConfluenceClient,
    page_id: str,
    mpp_path: Path,
    confirm: str,
    *,
    allow_live_ab: bool = False,
) -> ApplyResult:
    if not is_confirmed(confirm):
        raise PermissionError("Запись без подтверждения «лей»/«пиши»/«да» запрещена")
    page, gantt, _diff, _ = prepare_apply_diff(client, page_id, mpp_path, allow_live_ab=allow_live_ab)
    storage = page["body"]["storage"]["value"]
    macro = find_macro(storage)
    span = macro_span(storage)

    if mpp_path:
        csvs = export_csv(mpp_path)
        d1, d2, n, m = compute_itogo_from_csv(csvs.tasks_csv, csvs.assignments_csv)
    else:
        d1, d2, n, m = compute_itogo_from_gantt(gantt)

    if macro is None:
        macro_id, param_id, param_hash = new_macro_ids()
        macro_html = build_macro_html(macro_id, param_id, param_hash)
        storage = storage + macro_html
        span = macro_span(storage)
        storage = apply_itogo(storage, d1, d2, n, m, macro_start=span[0] if span else None)
        macro = find_macro(storage)
    else:
        storage = apply_itogo(storage, d1, d2, n, m, macro_start=span[0] if span else None)

    attachments = client.list_attachments(page_id)
    att = find_gantt_attachment(attachments, macro) if macro else None
    filename = macro.attachment_name if macro else "gantt-chart-unknown.json"
    new_ver = upload_gantt_json(client, page_id, filename, gantt, att)

    fresh = client.get_page(page_id, expand="version")
    version = int(fresh["version"]["number"])
    client.put_page(page_id, page["title"], storage, version)
    itogo_html = build_itogo_html(d1, d2, n, m)
    return ApplyResult(page_id, page["title"], page_url(page_id), new_ver, itogo_html)


def prepare_child_diff(
    client: ConfluenceClient,
    parent_id: str,
    title: str | None,
    mpp_path: Path | None,
    *,
    allow_live_ab: bool = False,
) -> tuple[str, dict[str, Any], str, bool]:
    _guard_page(parent_id, allow_live_ab)
    parent = client.get_page(parent_id)
    parent_title = parent["title"]
    child_title = title or default_child_title(parent_title)
    empty = False
    parent_macro = find_macro(parent["body"]["storage"]["value"])
    parent_gantt: dict[str, Any] | None = None
    if parent_macro:
        parent_gantt, _ = load_gantt_json(client, parent_id, parent_macro)

    if mpp_path:
        gantt = build_plan_from_mpp(mpp_path, parent_gantt)
        csvs = export_csv(mpp_path)
        d1, d2, n, m = compute_itogo_from_csv(csvs.tasks_csv, csvs.assignments_csv)
    elif parent_gantt:
        gantt = build_plan_copy_parent(parent_gantt)
        d1, d2, n, m = compute_itogo_from_gantt(gantt)
    else:
        gantt = build_plan_empty(child_title)
        d1, d2, n, m = compute_itogo_from_gantt(gantt)
        empty = True

    diff = build_diff(
        page_id=parent_id,
        title=parent_title,
        operation="создание дочерней страницы с макросом",
        gantt=gantt,
        child_title=child_title,
        empty_plan=empty,
    )
    return child_title, gantt, diff, empty


def create_child_with_plan(
    client: ConfluenceClient,
    parent_id: str,
    confirm: str,
    title: str | None = None,
    mpp_path: Path | None = None,
    *,
    allow_live_ab: bool = False,
) -> ApplyResult:
    if not is_confirmed(confirm):
        raise PermissionError("Запись без подтверждения «лей»/«пиши»/«да» запрещена")
    child_title, gantt, _diff, _ = prepare_child_diff(
        client, parent_id, title, mpp_path, allow_live_ab=allow_live_ab
    )
    if mpp_path:
        csvs = export_csv(mpp_path)
        d1, d2, n, m = compute_itogo_from_csv(csvs.tasks_csv, csvs.assignments_csv)
    else:
        d1, d2, n, m = compute_itogo_from_gantt(gantt)
    itogo_html = build_itogo_html(d1, d2, n, m)
    page, macro_id, _pid, _phash = create_child_page(client, parent_id, child_title, itogo_html)
    page_id = str(page["id"])
    filename = f"gantt-chart-{macro_id}.json"
    new_ver = upload_gantt_json(client, page_id, filename, gantt, None)
    return ApplyResult(page_id, child_title, page_url(page_id), new_ver, itogo_html)
