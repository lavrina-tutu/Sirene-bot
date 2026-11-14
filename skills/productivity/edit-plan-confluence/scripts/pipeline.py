"""Orchestration: preview / apply MPP plan to Confluence gantt page."""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from child_page import create_child_page, default_child_title
from conf_client import ConfluenceClient, ConfluenceError
from env import page_url
from gantt_attachment import find_gantt_attachment, load_gantt_json, upload_gantt_json, verify_uploaded
from gate_diff import build_diff, is_confirmed
from itogo import (
    apply_itogo,
    build_itogo_html,
    compute_itogo_from_csv,
    compute_itogo_from_gantt,
    record_itogo_observation,
)
from macro import build_macro_html, find_macro, macro_span, new_macro_ids
from mpp_calendar import calendar_from_mpp
from mpp_convert import copy_parent_gantt, convert_mpp_csv, empty_gantt
from mpp_input import export_csv
from plan_archive import resolve_plan_binding, store_artifact
from plan_receipt import read_receipt, write_receipt

import sys as _sys
from pathlib import Path as _Path

_MOFS_ROOT = _Path.home() / "USERTOOLS" / "MofsIndex"
if str(_MOFS_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_MOFS_ROOT))

from mofs_index.plan import writer as plan_writer  # noqa: E402

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
    drop_links: list[tuple[int, int]] | None = None,
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
        drop_links=drop_links,
    )


def gantt_critical_warning(gantt: dict[str, Any]) -> str | None:
    """Если плагин пересчитает срок проекта (критический путь по связям)
    быстрее/дольше, чем указано в корне (duration из MPP) — вернуть текст
    предупреждения. Плагин игнорирует start/end и живёт по цепочке связей."""
    from mpp_convert import critical_path_days

    root = gantt["eventsData"][0]
    mpp_dur = float(root.get("duration") or 0.0)
    plugin_dur = critical_path_days(gantt)
    if abs(mpp_dur - plugin_dur) >= 0.05:
        return (
            f"плагин покажет срок {plugin_dur:g} дней, а не {mpp_dur:g} из MPP "
            f"(критический путь по связям не совпадает с корнем). Если нужно "
            f"совпадение — исключи лишние зависимости через --drop-dep FROM:TO"
        )
    return None


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
    drop_links: list[tuple[int, int]] | None = None,
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
        gantt = build_plan_from_mpp(mpp_path, existing_gantt if existing_gantt else None, drop_links=drop_links)
        csvs = export_csv(mpp_path)
        d1, d2, n, m = compute_itogo_from_csv(csvs.tasks_csv, csvs.assignments_csv)
        w = gantt_critical_warning(gantt)
        if w:
            warnings.append(w)
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


def preflight_archive(
    page_id: str,
    mpp_path: Path | None,
    gantt: dict[str, Any],
    *,
    project_slug: str | None = None,
) -> dict[str, Any]:
    """P1.W1.4: сохранить исходные+подготовленные байты и зафиксировать
    попытку в SQL **до первого POST/PUT** (R-009 п.5).

    Возвращает контекст попытки (``attempt_id``, ``plan_id``, ``lineage_id``,
    ``prepared_sha256``) для последующих стадий apply/resume. Ошибка файловой
    записи или SQL commit останавливает публикацию (исключение всплывает
    наружу — ни один вызывающий код после этой функции не увидит частично
    записанного состояния: либо вся preflight-транзакция прошла, либо нет).
    """
    binding = resolve_plan_binding(page_id, project_slug)
    plan_id, lineage_id = binding["plan_id"], binding["lineage_id"]

    prepared_bytes = json.dumps(gantt, ensure_ascii=False).encode("utf-8")
    prepared_sha256 = hashlib.sha256(prepared_bytes).hexdigest()
    prepared_artifact_id, _ = store_artifact(
        prepared_bytes, "prepared_json", project_slug=binding["project_slug"],
    )

    mpp_artifact_id = None
    if mpp_path is not None:
        mpp_artifact_id, _ = store_artifact(
            Path(mpp_path), "mpp", project_slug=binding["project_slug"],
        )

    from mofs_index.db import connect_durable
    conn = connect_durable()
    try:
        attempt_id = plan_writer.begin_attempt(
            conn,
            plan_writer.AttemptSpec(
                plan_id=plan_id, lineage_id=lineage_id,
                source_namespace="confluence:dom.tutu.ru",
                prepared_sha256=prepared_sha256,
            ),
        )
        event_id = plan_writer.record_event(
            conn, attempt_id, "archive", "prepared",
            detail=f"prepared_sha256={prepared_sha256} mpp_artifact={mpp_artifact_id}",
        )
    finally:
        conn.close()

    write_receipt(attempt_id, event_id, {
        "stage": "archive",
        "status": "prepared",
        "page_id": page_id,
        "prepared_sha256": prepared_sha256,
        "prepared_artifact_id": prepared_artifact_id,
        "mpp_artifact_id": mpp_artifact_id,
    })

    return {
        "attempt_id": attempt_id,
        "plan_id": plan_id,
        "lineage_id": lineage_id,
        "prepared_sha256": prepared_sha256,
        "prepared_artifact_id": prepared_artifact_id,
    }


def _connect_plan_db():
    from mofs_index.db import connect_durable

    return connect_durable()


MAX_PUT_409_RETRIES = 3


def _patch_fresh_storage(
    fresh_storage: str,
    new_macro_html: str | None,
    d1: str,
    d2: str,
    n: int,
    m: int,
) -> str:
    """Применить макрос (если новый)/«Итого» к конкретному телу страницы."""
    storage = fresh_storage
    if new_macro_html is not None:
        storage = storage + new_macro_html
    span = macro_span(storage)
    return apply_itogo(storage, d1, d2, n, m, macro_start=span[0] if span else None)


def _put_page_with_409_retry(
    client: ConfluenceClient,
    page_id: str,
    new_macro_html: str | None,
    d1: str,
    d2: str,
    n: int,
    m: int,
    *,
    max_attempts: int = MAX_PUT_409_RETRIES,
) -> tuple[str, int, str]:
    """P1.W1.6-доб.: узкий retry вокруг ``put_page`` на HTTP 409 (AC-107).

    При конфликте версии (409) делается свежий GET ``body.storage,version`` и
    повторяется ТОЛЬКО эта стадия (переприменение макроса/«Итого» к новому
    телу) — не весь ``apply_plan`` (не повторный upload вложения, не повторный
    preflight-archive). Любая иная ошибка пробрасывается немедленно.
    Возвращает ``(title, new_version, patched_storage)`` финальной попытки.
    """
    last_exc: ConfluenceError | None = None
    for attempt in range(max_attempts):
        fresh = client.get_page(page_id, expand="body.storage,version")
        fresh_storage = fresh["body"]["storage"]["value"]
        fresh_version = int(fresh["version"]["number"])
        fresh_title = fresh.get("title")
        patched_storage = _patch_fresh_storage(fresh_storage, new_macro_html, d1, d2, n, m)
        try:
            client.put_page(page_id, fresh_title, patched_storage, fresh_version + 1)
            return fresh_title, fresh_version + 1, patched_storage
        except ConfluenceError as exc:
            if exc.status == 409 and attempt < max_attempts - 1:
                last_exc = exc
                continue
            raise
    assert last_exc is not None
    raise last_exc


def apply_plan(
    client: ConfluenceClient,
    page_id: str,
    mpp_path: Path,
    confirm: str,
    *,
    allow_live_ab: bool = False,
    drop_links: list[tuple[int, int]] | None = None,
    project_slug: str | None = None,
    archive: bool = True,
) -> ApplyResult:
    if not is_confirmed(confirm):
        raise PermissionError("Запись без подтверждения «лей»/«пиши»/«да» запрещена")
    page, gantt, _diff, _ = prepare_apply_diff(
        client, page_id, mpp_path, allow_live_ab=allow_live_ab, drop_links=drop_links
    )
    storage = page["body"]["storage"]["value"]
    macro = find_macro(storage)

    if mpp_path:
        csvs = export_csv(mpp_path)
        d1, d2, n, m = compute_itogo_from_csv(csvs.tasks_csv, csvs.assignments_csv)
    else:
        d1, d2, n, m = compute_itogo_from_gantt(gantt)

    # P1.W1.4 — preflight archive ДО первого POST/PUT (R-009 п.5). Только
    # для боевой записи (archive=True); юнит-тесты без MofsIndex/WorkVault
    # окружения могут явно отключить (archive=False) для изоляции.
    attempt_ctx = None
    if archive:
        attempt_ctx = preflight_archive(page_id, mpp_path, gantt, project_slug=project_slug)

    if macro is None:
        macro_id, param_id, param_hash = new_macro_ids()
        new_macro_html = build_macro_html(macro_id, param_id, param_hash)
        filename = f"gantt-chart-{param_id}.json"
    else:
        new_macro_html = None
        filename = macro.attachment_name

    attachments = client.list_attachments(page_id)
    att = find_gantt_attachment(attachments, macro) if macro else None
    prepared_bytes = json.dumps(gantt, ensure_ascii=False).encode("utf-8")
    expected_sha256 = hashlib.sha256(prepared_bytes).hexdigest()
    new_ver = upload_gantt_json(client, page_id, filename, gantt, att)

    # P1.W1.5 — version-specific GET, не latest; сверка hash (R-009 п.7, AC-105).
    verified, _raw = verify_uploaded(client, page_id, filename, new_ver, expected_sha256)
    attachment_conflict = not verified
    if attempt_ctx:
        conn = _connect_plan_db()
        try:
            event_id = plan_writer.record_event(
                conn, attempt_ctx["attempt_id"], "attachment_verify",
                "confirmed" if verified else "conflict",
                detail=f"attachment_version={new_ver} verified={verified}",
            )
        finally:
            conn.close()
        write_receipt(attempt_ctx["attempt_id"], event_id, {
            "stage": "attachment_verify",
            "status": "confirmed" if verified else "conflict",
            "attachment_version": new_ver,
            "expected_sha256": expected_sha256,
        })

    # P1.W1.6 — fresh-body patch: свежий GET body.storage,version,title
    # непосредственно перед PUT; патч применяется к свежему body, не к телу
    # из диффа (R-009 п.8, AC-107). Это исправление прежней ошибки, где
    # `fresh` запрашивал только версию, а storage бралось из устаревшего
    # диффа.
    # P1.W1.6-доб.: обёрнуто узким 409-retry — только эта стадия (fresh GET +
    # переприменение макроса/«Итого» + put_page), не весь apply (AC-107).
    fresh_title, new_page_version, fresh_storage = _put_page_with_409_retry(
        client, page_id, new_macro_html, d1, d2, n, m,
    )

    if attempt_ctx:
        conn = _connect_plan_db()
        try:
            plan_writer.set_attempt_status(conn, attempt_ctx["attempt_id"], "confirmed")
            event_id = plan_writer.record_event(
                conn, attempt_ctx["attempt_id"], "storage_put", "confirmed",
                detail=f"page_version={new_page_version}",
            )
            plan_writer.record_publication(
                conn,
                plan_writer.PublicationSpec(
                    plan_id=attempt_ctx["plan_id"],
                    lineage_id=attempt_ctx["lineage_id"],
                    artifact_id=attempt_ctx["prepared_artifact_id"],
                    source_namespace="confluence:dom.tutu.ru",
                    attachment_id=att.attach_id if att else filename,
                    attachment_version=new_ver,
                    page_id=str(page_id),
                    filename=filename,
                    page_version=new_page_version,
                    raw_sha256=expected_sha256,
                ),
            )
            # P1.W1.doб. (хвост AC-110): каждый apply автоматически пишет
            # plan_page_observation — не только явный внешний вызов.
            record_itogo_observation(
                attempt_ctx["plan_id"], str(page_id),
                page_version=new_page_version,
                raw_storage=fresh_storage,
                conn=conn,
            )
        finally:
            conn.close()
        write_receipt(attempt_ctx["attempt_id"], event_id, {
            "stage": "storage_put", "status": "confirmed",
            "page_version": new_page_version,
        })

    itogo_html = build_itogo_html(d1, d2, n, m)
    return ApplyResult(page_id, fresh_title, page_url(page_id), new_ver, itogo_html)


def prepare_child_diff(
    client: ConfluenceClient,
    parent_id: str,
    title: str | None,
    mpp_path: Path | None,
    *,
    allow_live_ab: bool = False,
    drop_links: list[tuple[int, int]] | None = None,
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
        gantt = build_plan_from_mpp(mpp_path, parent_gantt, drop_links=drop_links)
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
    drop_links: list[tuple[int, int]] | None = None,
    attempt_id: str | None = None,
) -> ApplyResult:
    """P1.W1.8: ``attempt_id`` — явный resume-ключ. Повторный вызов с тем же
    ``attempt_id`` после сбоя между POST страницы и upload вложения
    переиспользует уже созданную дочку (не плодит вторую, AC-109)."""
    if not is_confirmed(confirm):
        raise PermissionError("Запись без подтверждения «лей»/«пиши»/«да» запрещена")
    attempt_id = attempt_id or str(uuid.uuid4())
    child_title, gantt, _diff, _ = prepare_child_diff(
        client, parent_id, title, mpp_path,
        allow_live_ab=allow_live_ab, drop_links=drop_links,
    )
    if mpp_path:
        csvs = export_csv(mpp_path)
        d1, d2, n, m = compute_itogo_from_csv(csvs.tasks_csv, csvs.assignments_csv)
    else:
        d1, d2, n, m = compute_itogo_from_gantt(gantt)
    itogo_html = build_itogo_html(d1, d2, n, m)
    page, macro_id, param_id, _phash = create_child_page(
        client, parent_id, child_title, itogo_html, attempt_id=attempt_id,
    )
    page_id = str(page["id"])
    # 📌 вложение — по param_id (ac:parameter id), не macro-id
    filename = f"gantt-chart-{param_id}.json"
    new_ver = _upload_child_attachment_with_receipt(
        client, attempt_id, page_id, filename, gantt,
    )
    return ApplyResult(page_id, child_title, page_url(page_id), new_ver, itogo_html)


def _upload_child_attachment_with_receipt(
    client: ConfluenceClient,
    attempt_id: str | None,
    page_id: str,
    filename: str,
    gantt: dict[str, Any],
) -> int:
    """P1.W1.8-доб. (вторая половина AC-109): upload дочки обёрнут
    квитанцией ``child_upload``. Повтор с тем же ``attempt_id`` после сбоя
    между POST страницы и upload (но уже после успешного upload) не
    дублирует вложение — переиспользует зафиксированную версию."""
    if attempt_id:
        existing = read_receipt(attempt_id, "child_upload")
        if existing and existing.get("status") == "confirmed":
            return int(existing["attachment_version"])
        write_receipt(attempt_id, "child_upload", {
            "stage": "child_upload", "status": "prepared",
            "page_id": page_id, "filename": filename,
        })
    new_ver = upload_gantt_json(client, page_id, filename, gantt, None)
    if attempt_id:
        write_receipt(attempt_id, "child_upload", {
            "stage": "child_upload", "status": "confirmed",
            "page_id": page_id, "filename": filename,
            "attachment_version": new_ver,
        })
    return new_ver
