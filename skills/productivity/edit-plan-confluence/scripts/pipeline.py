"""Orchestration: preview / apply MPP plan to Confluence gantt page."""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass
from contextlib import ExitStack
from pathlib import Path
from typing import Any

from child_page import create_child_page, default_child_title
from conf_client import ConfluenceClient, ConfluenceError
from env import page_url
from gantt_attachment import (AttachmentInfo, UploadVerificationConflict, find_gantt_attachment,
                              load_gantt_json, upload_gantt_json, verify_uploaded, verify_current_attachment)
from gate_diff import build_diff, is_confirmed
from itogo import (
    apply_itogo,
    build_itogo_html,
    compute_itogo_from_csv,
    compute_itogo_from_gantt,
    parse_itogo_text,
)
from macro import build_macro_html, find_macro, macro_span, new_macro_ids
from mpp_calendar import calendar_from_mpp
from mpp_convert import copy_parent_gantt, convert_mpp_csv, empty_gantt
from mpp_input import export_csv
from plan_archive import resolve_plan_binding, store_artifact
from plan_receipt import read_receipt, write_receipt, write_failure_receipt
from plan_verify import (PublicationVerificationError, verify_attachment_bytes,
                         verify_storage_observation)

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
    """Limited legacy FS/zero-lag diagnostic; never a plugin prediction."""
    from copy import deepcopy
    from mpp_convert import critical_path_days
    roots=gantt.get('eventsData',[])
    if not roots:return 'Ограниченная диагностика longest-path: нет корня; schedule:not_verified'
    root = roots[0]
    def leaves(nodes):
        for node in nodes:
            if node.get('children'):yield from leaves(node['children'])
            elif not node.get('rollup') and node['id']!=root['id']:yield deepcopy(node)
    tasks=list(leaves(roots));keys={t['id'] for t in tasks}
    dependencies=[d for d in gantt.get('dependenciesData',[]) if d.get('active',True)]
    if not tasks or any(d.get('from') not in keys or d.get('to') not in keys or
                        d.get('type')!=2 or d.get('lag')!=0 for d in dependencies):
        return 'Ограниченная диагностика longest-path неприменима к этому профилю; schedule:not_verified'
    mpp_dur = float(root.get("duration") or 0.0)
    try:
        estimate = critical_path_days({'eventsData':tasks,'dependenciesData':dependencies})
    except (RecursionError,KeyError,TypeError,ValueError):
        return 'Ограниченная диагностика longest-path: неподдержанный граф; schedule:not_verified'
    if abs(mpp_dur - estimate) >= 0.05:
        return (
            f"Ограниченная модель FS/zero-lag: {estimate:g} дней; корень MPP: {mpp_dur:g}. "
            "Календари, ограничения и назначения не рассчитаны; это не результат плагина "
            "и не основание исключения связи; schedule:not_verified"
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


def _attempt_event(ctx, stage, status, payload):
    if ctx is None:
        return
    conn = _connect_plan_db()
    try:
        event_id = plan_writer.record_event(
            conn, ctx["attempt_id"], stage, status,
            detail=json.dumps(payload, ensure_ascii=False),
        )
    finally:
        conn.close()
    write_receipt(ctx["attempt_id"], event_id, {"stage": stage, "status": status, **payload})


def _verify_written_attachment(client, page_id, uploaded, expected_sha256):
    if not isinstance(uploaded, AttachmentInfo):
        raise UploadVerificationConflict("upload did not return actual attachment identity")
    ok, raw = verify_uploaded(
        client, page_id, uploaded.filename, uploaded.version, expected_sha256,
        attachment_id=uploaded.attach_id,
    )
    # Independently enforce both contracts: a False return is blocking even
    # if the bytes happen to match, and True cannot hide a byte mismatch.
    result = verify_attachment_bytes(raw, expected_sha256)
    if ok is not True or not result.ok:
        raise UploadVerificationConflict("uploaded attachment verification failed")
    return result


def _record_readback(ctx, page_id, observed, verification, evidence):
    if ctx is None:
        return None
    raw_storage = observed["body"]["storage"]["value"]
    d1, d2, n = parse_itogo_text(raw_storage)
    conn = _connect_plan_db()
    try:
        return plan_writer.record_page_observation(conn, plan_writer.PageObservationSpec(
            plan_id=ctx["plan_id"], page_id=str(page_id),
            page_version=int(observed["version"]["number"]),
            itogo_raw=raw_storage,
            itogo_text=f"Итого: с {d1} по {d2} - {n} рабочих дней" if d1 else None,
            itogo_d1=d1, itogo_d2=d2, itogo_n=n,
            quality="ok" if verification.ok else "unknown",
            verification_status="verified_observation" if verification.ok else "verification_failed",
            verification_scope=verification.scope,
            verification_profile=verification.profile,
            verification=evidence,
            storage_sha256=hashlib.sha256(observed["body"]["storage"]["value"].encode()).hexdigest(),
        ))
    finally:
        conn.close()


def _legacy_apply_plan(
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
        client, page_id, mpp_path, allow_live_ab=allow_live_ab, drop_links=drop_links,
    )
    macro = find_macro(page["body"]["storage"]["value"])
    if mpp_path:
        csvs = export_csv(mpp_path)
        d1, d2, n, m = compute_itogo_from_csv(csvs.tasks_csv, csvs.assignments_csv)
    else:
        d1, d2, n, m = compute_itogo_from_gantt(gantt)
    ctx = preflight_archive(page_id, mpp_path, gantt, project_slug=project_slug) if archive else None
    if macro is None:
        new_macro_html = build_macro_html(*new_macro_ids())
        expected_macro = find_macro(new_macro_html)
    else:
        new_macro_html = None
        expected_macro = macro
    filename = expected_macro.attachment_name
    att = find_gantt_attachment(client.list_attachments(page_id), expected_macro)
    expected_sha256 = hashlib.sha256(json.dumps(gantt, ensure_ascii=False).encode()).hexdigest()
    stage = "attachment_post"
    external_effect = "unknown"
    try:
        _attempt_event(ctx, stage, "prepared", {"page_id": page_id, "filename": filename,
                                              "published": None, "external_effect": external_effect})
        uploaded = upload_gantt_json(client, page_id, filename, gantt, att)
        external_effect = "partial"
        stage = "attachment_verify"
        attachment_check = _verify_written_attachment(client, page_id, uploaded, expected_sha256)
        _attempt_event(ctx, stage, "confirmed", {"attachment_id": uploaded.attach_id,
                       "attachment_version": uploaded.version, "expected_sha256": expected_sha256,
                       "published": None, "external_effect": external_effect, "scope": "attachment_version"})
        stage = "storage_put"
        _attempt_event(ctx, stage, "prepared", {"published": None, "external_effect": external_effect})
        fresh_title, written_version, intended_storage = _put_page_with_409_retry(
            client, page_id, new_macro_html, d1, d2, n, m,
        )
        stage = "storage_verify"
        # Only a new GET is evidence; the PUT response/intended text isn't.
        observed = client.get_page(page_id, expand="body.storage,version")
        check = verify_storage_observation(
            observed["body"]["storage"]["value"], expected_storage=intended_storage,
            expected_macro=expected_macro, expected_itogo=(d1, d2, n),
            expected_version=written_version, actual_version=int(observed["version"]["number"]),
        )
        evidence = asdict(check)
        evidence["attachment"] = {
            "attachment_id": uploaded.attach_id, "attachment_version": uploaded.version,
            "expected_sha256": expected_sha256, "actual_sha256": attachment_check.actual_sha256,
        }
        if check.ok:
            # The exact uploaded version can still match after a foreign
            # latest version appeared. Verify the current target separately.
            verify_current_attachment(client, page_id, uploaded, expected_sha256)
        observation_id = _record_readback(ctx, page_id, observed, check, evidence)
        if not check.ok:
            raise PublicationVerificationError("storage read-back failed: " + ", ".join(check.errors))
        _attempt_event(ctx, stage, "confirmed", {"page_version": written_version,
                       "observation_id": observation_id, "scope": "current_state",
                       "published": None, "external_effect": external_effect})
        if ctx:
            conn = _connect_plan_db()
            try:
                publication_id = plan_writer.record_publication(conn, plan_writer.PublicationSpec(
                    plan_id=ctx["plan_id"], lineage_id=ctx["lineage_id"],
                    artifact_id=ctx["prepared_artifact_id"], source_namespace="confluence:dom.tutu.ru",
                    attachment_id=uploaded.attach_id, attachment_version=uploaded.version,
                    page_id=str(page_id), macro_id=expected_macro.macro_id, filename=filename,
                    page_version=written_version, raw_sha256=expected_sha256,
                    observation_id=observation_id,
                    # This legacy path has no full admission/snapshot proof.
                    trust="legacy_unverified",
                ))
                plan_writer.set_attempt_status(conn, ctx["attempt_id"], "confirmed")
            finally:
                conn.close()
            write_receipt(ctx["attempt_id"], "publication_readback", {
                "stage": "storage_verify", "status": "confirmed", "published": True,
                "external_effect": "confirmed", "scope": "current_state",
                "verification_profile": check.profile, "publication_trust": "legacy_unverified",
                "publication_id": publication_id, "observation_id": observation_id,
                "schedule": "not_verified", "page_version": written_version,
            })
    except Exception as exc:
        if ctx:
            conn = _connect_plan_db()
            try:
                plan_writer.set_attempt_status(conn, ctx["attempt_id"], "failed")
            finally:
                conn.close()
            _attempt_event(ctx, stage, "failed", {"published": None, "external_effect": external_effect,
                                                   "error": str(exc)})
            write_failure_receipt(ctx["attempt_id"], stage, exc, external_effect=external_effect)
        raise
    return ApplyResult(page_id, fresh_title, page_url(page_id), uploaded.version,
                       build_itogo_html(d1, d2, n, m))


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
    # Creating the page is already an external effect. Any later failure
    # remains unconfirmed and must be visible in the operation receipt.
    stage = "page_create"
    external_effect = "unknown"
    try:
        page, macro_id, param_id, phash = create_child_page(
            client, parent_id, child_title, itogo_html, attempt_id=attempt_id,
        )
        external_effect = "partial"
        page_id = str(page["id"])
        filename = f"gantt-chart-{param_id}.json"
        stage = "child_upload"
        new_ver = _upload_child_attachment_with_receipt(client, attempt_id, page_id, filename, gantt)
        stage = "storage_verify"
        expected_html = itogo_html + build_macro_html(macro_id, param_id, phash)
        created = read_receipt(attempt_id, "page_create") or {}
        expected_version = created.get("page_version")
        if type(expected_version) is not int:
            raise PublicationVerificationError("no recorded child page version")
        observed = client.get_page(page_id, expand="body.storage,version")
        check = verify_storage_observation(
            observed["body"]["storage"]["value"], expected_storage=expected_html,
            expected_macro=find_macro(expected_html), expected_itogo=(d1, d2, n),
            expected_version=expected_version, actual_version=int(observed["version"]["number"]),
        )
        if not check.ok:
            raise PublicationVerificationError("child storage read-back failed: " + ", ".join(check.errors))
        upload_receipt = read_receipt(attempt_id, "child_upload")
        uploaded = AttachmentInfo(upload_receipt["attachment_id"], filename, new_ver, filename)
        verify_current_attachment(client, page_id, uploaded,
                                  hashlib.sha256(json.dumps(gantt, ensure_ascii=False).encode()).hexdigest())
        write_receipt(attempt_id, "child_complete", {
            "stage": stage, "status": "confirmed", "published": True,
            "external_effect": "confirmed", "scope": "current_state",
            "verification": asdict(check), "schedule": "not_verified",
            "publication_trust": "legacy_unverified", "page_id": page_id,
            "page_version": expected_version, "attachment_version": new_ver,
        })
    except Exception as exc:
        write_failure_receipt(attempt_id, stage, exc, external_effect=external_effect)
        raise
    return ApplyResult(page_id, child_title, page_url(page_id), new_ver, itogo_html)


def _upload_child_attachment_with_receipt(
    client: ConfluenceClient, attempt_id: str | None, page_id: str,
    filename: str, gantt: dict[str, Any],
) -> int:
    expected_sha256 = hashlib.sha256(json.dumps(gantt, ensure_ascii=False).encode()).hexdigest()
    existing = read_receipt(attempt_id, "child_upload") if attempt_id else None
    if existing and existing.get("attachment_version"):
        if existing.get("page_id") != page_id or existing.get("filename") != filename:
            raise UploadVerificationConflict("child upload receipt target mismatch")
        # Old receipts contain no ID. Resolve the current exact name, then
        # verify the recorded version as well as the currently used version.
        attach_id = existing.get("attachment_id")
        if not attach_id:
            matches = [a for a in client.list_attachments(page_id) if a.get("title") == filename]
            if len(matches) != 1:
                raise UploadVerificationConflict("child receipt attachment missing/ambiguous")
            attach_id = str(matches[0]["id"])
        uploaded = AttachmentInfo(attach_id, filename, int(existing["attachment_version"]), filename)
    else:
        # A lost upload response must be reconciled by exact bytes before a
        # second POST, including the preserved non-MPP child adapter.
        pending=None
        if existing:
            if (existing.get('page_id')!=page_id or existing.get('filename')!=filename
                    or existing.get('expected_sha256')!=expected_sha256):
                raise UploadVerificationConflict('child upload intent incomplete or changed')
            pending=find_gantt_attachment(client.list_attachments(page_id),
                type('ChildTarget',(),{'attachment_name':filename})())
            if pending:
                _verify_written_attachment(client,page_id,pending,expected_sha256)
                verify_current_attachment(client,page_id,pending,expected_sha256)
        if attempt_id:
            write_receipt(attempt_id, "child_upload", {
                "stage": "child_upload", "status": "prepared", "published": None,
                "external_effect": "partial", "page_id": page_id, "filename": filename,
                'expected_sha256':expected_sha256,
            })
        uploaded = pending or upload_gantt_json(client, page_id, filename, gantt, None)
        if not isinstance(uploaded, AttachmentInfo):
            raise UploadVerificationConflict("missing actual child attachment identity")
        if attempt_id:
            write_receipt(attempt_id, "child_upload", {
                "stage": "child_upload", "status": "prepared", "published": None,
                "external_effect": "partial", "page_id": page_id, "filename": filename,
                "attachment_id": uploaded.attach_id, "attachment_version": uploaded.version,
                'expected_sha256':expected_sha256,
            })
    _verify_written_attachment(client, page_id, uploaded, expected_sha256)
    verify_current_attachment(client, page_id, uploaded, expected_sha256)
    if attempt_id:
        write_receipt(attempt_id, "child_upload", {
            "stage": "child_upload", "status": "confirmed", "published": None,
            "external_effect": "partial", "scope": "attachment_version",
            "page_id": page_id, "filename": filename, "attachment_id": uploaded.attach_id,
            "attachment_version": uploaded.version, "expected_sha256": expected_sha256,
        })
    return uploaded.version


# Stage 09 public prepared branch. Legacy helpers above remain for compatibility
# tests and child-page support; the CLI's MPP diff/publish/apply share this path.
@dataclass
class PublishPreparation:
    receipt: dict
    counters: dict
    context: Any = None
    operation: Any = None
    result_id: str | None = None
    conversion: dict | None = None
    target: dict | None = None

    @property
    def exit_code(self):
        return self.receipt['exit_code']

    def to_dict(self):
        return json.loads(json.dumps(self.receipt))


def _publish_error(receipt, code, rc=5):
    receipt.update(status='needs_decision' if rc==3 else 'conflict' if rc==4 else 'failed',exit_code=rc,
                   error={'code':code,'message':code,'retryable':False,
                          'next_action':'operation show --operation-id '+str(receipt['operation_id']) if receipt['operation_id'] else 'diff --project-slug <slug>'})
    return receipt


def _current_target(client, page_id):
    from prepared_plan import fingerprint
    from dataclasses import asdict
    from plan_verify import managed_state
    page=client.get_page(page_id)
    if str(page.get('id'))!=str(page_id):
        raise ValueError('target_page_mismatch')
    storage=page['body']['storage']['value']; macro=find_macro(storage)
    attachments=client.list_attachments(page_id) if macro else []
    att=find_gantt_attachment(attachments,macro) if macro else None
    target={'page_id':str(page_id),'page_version':int(page['version']['number']),
            'storage_sha256':hashlib.sha256(storage.encode()).hexdigest(),
            'managed':managed_state(storage),
            'macro':asdict(macro) if macro else None,'attachment':asdict(att) if att else None}
    target['sha256']=fingerprint(target)
    return page,target


def _prepared_source(conn, operation, context, request, counters, export=None):
    from env import Settings, select_mpxj_python
    from plan_save import run_export_full
    from plan_cache import ParseCache
    from prepared_plan import PreparedPlan, NormalizationProfile, validate_export
    from plan_operation import freeze_operation_input
    from plan_context import PROFILES
    from mofs_index.plan import query as q
    frozen=freeze_operation_input(conn,operation)
    if export is None:
        runtime=select_mpxj_python(settings=Settings(context.settings,context.sources))
        material=ParseCache.material(frozen.sha256,reader=runtime.versions,export_version='full-export-v2')
        cache=ParseCache(context.cache_dir,counters=counters)
        try:
            export=cache.get_or_parse(frozen.mpp_path,material,parser=lambda source:run_export_full(source,context=context,runtime=runtime,
                diagnostics_dir=context.workvault/'_plan-receipts'/operation.operation_id/operation.attempt_id))
        except Exception:
            counters['MPXJ_read']=None
            raise
    validate_export(export)
    if export['provenance']['sha256']!=frozen.sha256 or export['provenance']['size_bytes']!=frozen.size_bytes:
        from plan_save import PlanSaveError
        raise PlanSaveError('source_hash_mismatch',exit_code=4)
    path=PROFILES/(context.settings['NORMALIZATION_PROFILE']+'.json')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=context.snapshot()['profiles']['NORMALIZATION_PROFILE']['sha256']:
        from plan_save import PlanSaveError
        raise PlanSaveError('normalization_profile_changed',exit_code=4)
    prepared=PreparedPlan.from_export(export,profile=NormalizationProfile.load(path),timezone_hint=request.get('timezone_hint'),
        provenance={'original_name':frozen.original_name,'source_path':frozen.original_locator})
    write_receipt(operation.operation_id,'source-prepared',prepared.to_dict(),workvault=context.workvault)
    return prepared,frozen


def _archive_publish_source(conn, operation, prepared, frozen, binding, context):
    from prepared_plan import canonical_bytes
    from mofs_index.plan.ingest_mpp import build_snapshot_spec
    aid,digest=store_artifact(frozen.mpp_path,'mpp',project_slug=binding['project_slug'],conn=conn,workvault=context.workvault)
    if digest!=frozen.sha256:raise ValueError('source_hash_mismatch')
    spec=build_snapshot_spec(prepared.to_dict(),plan_id=binding['plan_id'],lineage_id=binding['lineage_id'],source_artifact_id=aid)
    store_artifact(spec.source_json.encode(),'export_json',ext='json',project_slug=binding['project_slug'],conn=conn,workvault=context.workvault)
    committed=plan_writer.commit_import_snapshot(conn,operation.item_id,operation.attempt_id,spec)
    # Set the ID in durable SQL first. Even a failed read-back retains it.
    return committed.snapshot_id


def _load_publish_prepared(conn, prep):
    from prepared_plan import PreparedPlan
    path=plan_writer.verify_artifact(conn,prep['prepared_artifact_id'])
    return PreparedPlan(json.loads(Path(path).read_text())).validate()


def _publish_readback(conn, snapshot_id):
    from mofs_index.plan import query as q
    plan_writer.verify_snapshot(conn,snapshot_id)
    snapshot=q.get_snapshot(conn,snapshot_id)
    artifact=q.find_artifact_by_hash(conn,snapshot['normalized_data_sha256'])
    if not artifact:raise ValueError('normalized_export_missing')
    path=plan_writer.verify_artifact(conn,artifact['artifact_id'],snapshot['normalized_data_sha256'])
    if Path(path).read_bytes()!=snapshot['source_json'].encode():raise ValueError('normalized_export_mismatch')


def prepare_publish(client=None, page_id=None, mpp_path=None, *, project_slug=None, lineage_id=None,
                    timezone_hint=None, drop_links=None, allow_live_ab=False, context=None,
                    db_path=None, workvault=None, cache_dir=None, operation_id=None,
                    mapping_revision=None, accept_proposal=None, reason=None, rule_scope='once',
                    export=None, plugin_profile=None, child=False, title=None):
    """Freeze → prepared → project/target → snapshot/read-back → identity/rules/admission.

    No POST/PUT. Resume reads durable prepared artifacts, never the original path.
    """
    from prepared_plan import PreparedPlan, canonical_bytes, fingerprint
    from plan_context import PlanContext, PROFILES
    from plan_save import validate_save_arguments, _failure
    from plan_operation import begin_import, ImportOperation
    from plan_receipt import single_receipt, mask_secrets, validate_single_receipt
    from mofs_index.db import connect_durable
    from mofs_index.plan import query as q, identity as identity
    from mofs_index.plan.migrate import ensure_plan_schema
    from mofs_index.plan.ingest_mpp import build_snapshot_spec
    from mpp_convert import convert_prepared_plan, representation_bytes
    from plugin_profile import PluginProfile
    from plan_diagnostics import diagnose, finding, compact_receipt_diagnostics
    from plan_policy import evaluate, POLICY_VERSION
    from plan_rules import apply_rules, resolve_drop_links, relation_signature, task_context, RULES_VERSION
    receipt=single_receipt(project_slug=project_slug);receipt['mode']='publish'
    counters=dict(MPXJ_read=0,cache_hit=0,cache_miss=0,POST=0,PUT=0)
    outcome=PublishPreparation(receipt,counters);conn=None
    try:
        validate_save_arguments(timezone_hint=timezone_hint)
        context=context or PlanContext.resolve(db=db_path,workvault=workvault,cache_dir=cache_dir)
        outcome.context=context
        conn=connect_durable(context.db);ensure_plan_schema(conn)
        previous=None
        if operation_id:
            op=q.get_operation(conn,operation_id); item=q.get_operation_item(conn,operation_id)
            if not op or not item or op['action']!='publish' or item['batch_id']:
                return PublishPreparation(_publish_error(receipt,'operation_context_incomplete',4),counters)
            previous=q.get_preparation(conn,operation_id)
            saved=json.loads(op['context_json'])
            context=PlanContext.from_snapshot(saved);outcome.context=context
            from plan_batch import _check_paths
            _check_paths(saved,workvault=workvault,cache_dir=cache_dir)
            if str(context.db)!=str(Path(db_path).resolve()) if db_path is not None else False:
                raise ValueError('operation_context_conflict')
            request=dict(previous['request'] if previous else saved.get('publish') or {})
            if not request.get('page_id'):
                raise ValueError('operation_context_incomplete')
            if not request.get('project_slug') and not op['plan_id']:
                raise ValueError('operation_context_incomplete')
            operation=ImportOperation(operation_id,item['item_id'],plan_writer.begin_operation_attempt(conn,operation_id,item['item_id']))
            outcome.operation=operation
            receipt.update(operation_id=operation_id,item_id=item['item_id'],snapshot_id=previous['snapshot_id'] if previous else item['snapshot_id'],
                project_slug=request.get('project_slug'))
            if q.publish_external_effect(conn,operation_id):
                receipt.update(published=None,external_effect='unknown')
            _guard_page(request['page_id'],allow_live_ab)
            binding=resolve_plan_binding(request['page_id'],request.get('project_slug'),
                lineage_id=request.get('lineage_id'),conn=conn)
            if not request.get('project_slug') or binding['plan_id']!=op['plan_id']:
                raise ValueError('operation_context_incomplete')
            last=q.get_preparation_result(conn,operation_id)
            if last and last['state']=='admitted' and not any((timezone_hint,mapping_revision,accept_proposal)):
                # Reconciliation uses the admitted immutable result, not a new
                # preparation based on the already changed remote state.
                return PublishPreparation(last['result']['receipt'],counters,context,operation,last['result_id'],
                                          target=last['result']['target'])
            if q.publish_external_effect(conn,operation_id):
                raise ValueError('operation_context_incomplete')
        else:
            request=dict(page_id=str(page_id),project_slug=project_slug,lineage_id=lineage_id,
                         timezone_hint=timezone_hint,drop_links=drop_links or [],child=child,title=title)
            operation=begin_import(conn,mpp_path,context={**context.snapshot(),'publish':request},action='publish')
            item=q.get_import_item(conn,operation.item_id)
        outcome.operation=operation
        receipt.update(operation_id=operation.operation_id,item_id=operation.item_id)
        page_id=request['page_id'];_guard_page(page_id,allow_live_ab)
        revision=previous['revision'] if previous else 1
        if previous:
            prepared=_load_publish_prepared(conn,previous)
            receipt['snapshot_id']=previous['snapshot_id']
            _publish_readback(conn,previous['snapshot_id'])
            receipt['verification']['archive']='verified'
            if timezone_hint is not None:
                old=q.get_preparation_result(conn,operation.operation_id)
                if prepared.normalized_data['resolved_timezone'] is not None or not old or not any(b['category']=='timezone' for b in old['admission']['blockers']):
                    raise ValueError('timezone_revision_forbidden')
                data=prepared.normalized_data
                prepared=PreparedPlan.from_export({**data,'provenance':data['source_identity'],'timezone_hint':None},
                    timezone_hint=timezone_hint,provenance=prepared.document['provenance'])
                request['timezone_hint']=timezone_hint;revision+=1
                snapshot=q.get_snapshot(conn,previous['snapshot_id'])
                spec=build_snapshot_spec(prepared.to_dict(),plan_id=op['plan_id'],lineage_id=op['lineage_id'],source_artifact_id=snapshot['source_artifact_id'])
                store_artifact(spec.source_json.encode(),'export_json',ext='json',project_slug=request['project_slug'],conn=conn,workvault=context.workvault)
                receipt['snapshot_id']=plan_writer.ingest_snapshot(conn,spec)
                _publish_readback(conn,receipt['snapshot_id'])
        else:
            prepared,frozen=_prepared_source(conn,operation,context,request,counters,export)
            receipt['source']={'name':frozen.original_name,'sha256':frozen.sha256,'size_bytes':frozen.size_bytes}
            receipt['completed_stages']=['input_frozen','prepared']
        # Project resolution and read-only target validation precede snapshot creation.
        binding=resolve_plan_binding(page_id,request.get('project_slug'),lineage_id=request.get('lineage_id'),conn=conn)
        request.update(project_slug=binding['project_slug'],lineage_id=binding['lineage_id'])
        publication_profiles={name:hashlib.sha256((PROFILES/name).read_bytes()).hexdigest()
                              for name in ('publication-policy-v1.json','project-rules-v1.json')}
        if previous and request.get('publication_profiles')!=publication_profiles:
            raise ValueError('operation_context_conflict')
        request['publication_profiles']=publication_profiles
        if not previous:
            request['rule_revisions']=[{'rule_id':r['rule_id'],'revision':r['revision'],'content_sha256':r['content_sha256']}
                                       for r in q.get_project_rules(conn,binding['project_slug'])]
        receipt['project_slug']=binding['project_slug']
        client=client or ConfluenceClient()
        page,target=_current_target(client,page_id)
        outcome.target=target
        if not previous:
            receipt['snapshot_id']=_archive_publish_source(conn,operation,prepared,frozen,binding,context)
            _publish_readback(conn,receipt['snapshot_id'])
        receipt['verification']['archive']='verified'
        receipt['completed_stages']=['input_frozen','prepared','archived']
        item=q.get_operation_item(conn,operation.operation_id)
        receipt['source']={'name':item['original_name'],'sha256':item['source_mpp_sha256'],'size_bytes':item['size_bytes']}
        prep_artifact,_=store_artifact(canonical_bytes(prepared.to_dict()),'prepared_json',ext='json',project_slug=request['project_slug'],conn=conn,workvault=context.workvault)
        plan_writer.record_preparation(conn,plan_writer.PreparationSpec(operation.operation_id,revision,receipt['snapshot_id'],
            prep_artifact,context.snapshot(),request))
        # A target change invalidates old proposals/decisions even before effects.
        prior_result=q.get_preparation_result(conn,operation.operation_id)
        if previous and prior_result and prior_result['result']['target']['sha256']!=target['sha256']:
            return PublishPreparation(_publish_error(receipt,'target_conflict',4),counters,context,operation,target=target)
        profile_error=None
        try:
            for name in ('NORMALIZATION_PROFILE','SUMMARY_PROFILE','PLUGIN_PROFILE'):
                p=PROFILES/(context.settings[name]+'.json')
                expected=context.snapshot()['profiles'][name]['sha256']
                if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=expected:
                    raise ValueError('preparation_profile_changed')
            profile=plugin_profile or PluginProfile.load(PROFILES/(context.settings['PLUGIN_PROFILE']+'.json'))
            profile.validate()
            conversion=convert_prepared_plan(prepared,plugin_profile=profile)
        except (ValueError,OSError) as exc:
            profile_error=getattr(exc,'code','plugin_profile_required');profile=None
            # Keep primary archive useful even with an unavailable target profile.
            conversion={'gantt':{},'mappings':{'tasks':{},'dependencies':{}},'diagnostics':[],
                        'summary':{'counts':{},'work':{},'reasons':[]}}
        findings=[];rules=[];excluded=[]
        if profile is not None:
            conversion,rules,findings,excluded=apply_rules(conn,operation.operation_id,prepared,conversion,mapping_revision=mapping_revision)
            diagnostics=diagnose(prepared,conversion,plugin_profile=profile,excluded=excluded)
            findings+=diagnostics['findings']
        else:
            diagnostics={'findings':[],'dates':[],'local_model':{'status':'unsupported'}}
            findings.append(finding('plugin_unknown',profile_error,'plugin'))
        # A legacy --drop-dep is an addressable proposal, never an instruction to
        # silently delete. Its local IDs are resolved once against this hash.
        proposed=resolve_drop_links(prepared.normalized_data,request.get('drop_links'))
        basis=fingerprint({'source':prepared.semantic_hash,'target':target,'policy':POLICY_VERSION,
            'rules':rules,'profile':profile.fingerprint if profile else None,'conversion':conversion})
        proposals=[{'action':'exclude_dependency','finding_sha256':fingerprint(f),
                    'losses':['Историческое адресное правило '+rule['rule_id']+'; сначала требуется identity confirm']}
                   for rule in rules if rule.get('pending_cause')
                   for f in findings if f['code']==rule['pending_cause']]
        for drop in proposed:
            matches=[f for f in findings if f['category'] in ('graph','unsupported_semantics') and
                     (f['entity']==drop['dependency_key'] or f['code']=='cycle')]
            addressed=matches or [finding('unsupported_semantics','explicit_dependency_exclusion',drop['dependency_key'],drop)]
            if not matches:findings+=addressed
            for f in addressed:
                proposal={**drop,'action':'exclude_dependency','finding_sha256':fingerprint(f),'basis_sha256':basis,
                    'snapshot_id':receipt['snapshot_id'],'policy_revision':POLICY_VERSION,
                    'losses':['Исключение одной точно указанной исходной связи только из представления Confluence']}
                tasks={t['task_key']:t for t in prepared.normalized_data['tasks']}
                proposal['project_rule']={'predecessor_key':drop['predecessor_key'],'successor_key':drop['successor_key'],
                    'expected_relation':drop['expected_relation'],
                    'task_contexts':{k:task_context(tasks[k]) for k in (drop['predecessor_key'],drop['successor_key'])},
                    'action':'exclude_dependency','policy_revision':POLICY_VERSION,
                    'termination':'Identity, task context, original relation or the addressed cause is no longer proven',
                    'cause':{'code':f['code'],'entity':drop['dependency_key'],'source_sha256':fingerprint(drop['expected_relation']),
                             'exact_source_required':drop['source_sha256'] if not matches else None}}
                pid=plan_writer.record_publish_proposal(conn,plan_writer.PublishProposalSpec(operation.operation_id,revision,proposal))
                proposals.append({**proposal,'proposal_id':pid})
        for f in findings:
            if f['category']=='date_mismatch':
                proposal={'action':'accept_date_deviation','finding_sha256':fingerprint(f),'basis_sha256':basis,
                    'snapshot_id':receipt['snapshot_id'],'source_sha256':receipt['source']['sha256'],
                    'policy_revision':POLICY_VERSION,'entity':f['entity'],
                    'expected_dates':{'source':f['source'],'represented':f['represented'],'observed':f['observed']},
                    'losses':['Сохранить точно перечисленное отклонение дат; schedule:accepted_deviation']}
                pid=plan_writer.record_publish_proposal(conn,plan_writer.PublishProposalSpec(operation.operation_id,revision,proposal))
                proposals.append({**proposal,'proposal_id':pid})
        if accept_proposal:
            # Recompute current basis before accepting a stored proposal.
            saved_proposals=q.get_publish_proposals(conn,operation.operation_id)
            selected=next((p for p in saved_proposals if p['proposal_id']==accept_proposal),None)
            if not selected or selected['content']['basis_sha256']!=basis:raise ValueError('proposal_context_mismatch')
            plan_writer.register_publish_decision(conn,plan_writer.PublishDecisionSpec(operation.operation_id,accept_proposal,reason,rule_scope))
        decisions=q.get_publish_proposals(conn,operation.operation_id)
        accepted_deviations=[];decision_ids=[]
        for proposal in decisions:
            p=proposal['content']
            if not proposal['decision_id'] or p['basis_sha256']!=basis:continue
            decision_ids.append(proposal['decision_id'])
            if p['action']=='exclude_dependency':
                if p['source_sha256']!=prepared.normalized_data['source_identity']['sha256']:raise ValueError('proposal_context_mismatch')
                depid=conversion['mappings']['dependencies'].get(p['dependency_key'])
                conversion['gantt']['dependenciesData']=[d for d in conversion['gantt']['dependenciesData'] if d['id']!=depid]
                conversion['diagnostics']=[d for d in conversion['diagnostics'] if d.get('entity')!=p['dependency_key']]
                excluded.append(p['dependency_key'])
                if proposal['rule_scope']=='project':
                    from plan_decision import persist_project_rule
                    persist_project_rule(conn,proposal,project_slug=request['project_slug'],workvault=context.workvault)
            elif p['action']=='accept_date_deviation':accepted_deviations.append(p['finding_sha256'])
        if decision_ids:
            # No severity override: diagnose the transformed representation again.
            findings=[f for f in findings if f['category']=='identity']
            diagnostics=diagnose(prepared,conversion,plugin_profile=profile,excluded=excluded)
            findings+=diagnostics['findings']
        admission=evaluate(findings,proposals=proposals,accepted_deviations=accepted_deviations)
        receipt.update(status=admission['status'],exit_code=admission['exit_code'],
            exceptions=[{'rule_id':r['rule_id'],'revision':r['rule_revision'],
                         'result':r['status'],'evidence_id':r['evidence_id']} for r in rules])
        receipt['verification']['schedule'],receipt['warnings']=compact_receipt_diagnostics(admission)
        counts=conversion['summary'].get('counts',{})
        for key in ('task_count','display_task_count','dependency_count'):receipt[key]=counts.get(key)
        if admission['blockers']:
            _publish_error(receipt,admission['blockers'][0]['code'],admission['exit_code'])
        raw=representation_bytes(conversion) if profile else None
        representation=None
        if raw is not None:
            representation,digest=store_artifact(raw,'prepared_json',ext='json',project_slug=request['project_slug'],conn=conn,workvault=context.workvault)
        evidence={'snapshot_id':receipt['snapshot_id'],'archive':'verified','admission':admission,'context':context.snapshot(),
            'profiles':{'plugin':profile.document if profile else None,'policy':diagnostics.get('profile'),
                        'normalization':json.loads((PROFILES/(context.settings['NORMALIZATION_PROFILE']+'.json')).read_text()),
                        'converter_version':conversion.get('converter_version'),
                        'historical_rules':json.loads((PROFILES/'project-rules-v1.json').read_text()),
                        'summary':json.loads((PROFILES/'summary-v1.json').read_text()),'rules_version':RULES_VERSION},
            'rules':rules,'decisions':decision_ids,'diagnostics':diagnostics,'target':target,
            'representation_sha256':hashlib.sha256(raw).hexdigest() if raw is not None else None}
        eid,_=store_artifact(canonical_bytes(evidence),'admission_evidence',ext='json',project_slug=request['project_slug'],conn=conn,workvault=context.workvault)
        receipt['verification']['schedule'],receipt['warnings']=compact_receipt_diagnostics(admission,eid)
        if admission['allowed']:receipt['completed_stages'].append('admitted')
        result={'receipt':receipt,'target':target,'basis_sha256':basis,'summary':conversion['summary']}
        validate_single_receipt(receipt)
        outcome.result_id=plan_writer.record_preparation_result(conn,plan_writer.PreparationResultSpec(operation.operation_id,revision,
            representation,eid,admission,result))
        plan_writer.record_operation_event(conn,operation.attempt_id,'publish_preparation',detail=outcome.result_id)
        outcome.conversion=conversion
        write_receipt(operation.operation_id,'publish-preparation-'+str(revision),receipt,workvault=context.workvault)
    except Exception as exc:
        if isinstance(exc,identity.IdentityError):_publish_error(receipt,exc.code,exc.exit_code)
        elif isinstance(exc,ValueError) and str(exc) in ('timezone_revision_forbidden','target_conflict','proposal_context_mismatch',
                'operation_context_conflict','operation_context_incomplete','preparation_revision_conflict'):
            _publish_error(receipt,str(exc),4)
        else:_failure(receipt,exc)
        if getattr(exc,'candidates',None) and outcome.operation:
            try:
                diagnostic=write_receipt(outcome.operation.operation_id,'input-error',
                    {'code':receipt['error']['code'],'candidates':list(exc.candidates)},workvault=context.workvault)
                receipt['error']['next_action']='Выбрать один MPP; список кандидатов: '+str(diagnostic)
            except OSError:
                _publish_error(receipt,'input_diagnostic_unavailable')
        if receipt['snapshot_id'] and receipt['verification']['archive']!='verified':receipt['verification']['archive']='failed'
        if conn is not None and outcome.operation:
            try:
                item=q.get_operation_item(conn,outcome.operation.operation_id)
                if item:
                    receipt['source']={'name':item['original_name'],'sha256':item['source_mpp_sha256'],'size_bytes':item['size_bytes']}
                    receipt['snapshot_id']=receipt['snapshot_id'] or item['snapshot_id']
                    if not item['snapshot_id']:
                        plan_writer.fail_import_item(conn,item['item_id'],outcome.operation.attempt_id,receipt['error']['code'])
                plan_writer.record_operation_event(conn,outcome.operation.attempt_id,'publish_preparation_error',status='failed',
                    detail=json.dumps({'exception_type':type(exc).__name__,'http_status':getattr(exc,'status',None),
                                       'errno':getattr(exc,'errno',None)}))
                plan_writer.record_operation_event(conn,outcome.operation.attempt_id,'publish_preparation_failed',status='failed',detail=json.dumps(receipt))
                write_receipt(outcome.operation.operation_id,'publish-failed',receipt,workvault=context.workvault)
            except Exception:pass # Original failure remains; never starts the network.
        if receipt['error']['code']=='project_slug_required':
            receipt.update(operation_id=None,item_id=None) # Intake is retained, not resumable for publication.
    finally:
        if conn is not None:conn.close()
    outcome.receipt=mask_secrets(receipt)
    return outcome


def _upload_prepared_bytes(client,page_id,filename,raw,existing):
    from gantt_attachment import upload_prepared_bytes
    return upload_prepared_bytes(client,page_id,filename,raw,existing,hashlib.sha256(raw).hexdigest())


def _verify_stage09_attachment(client,page_id,uploaded,expected):
    """Compatibility hook: exact recorded version plus independent current ID/version."""
    current=find_gantt_attachment(client.list_attachments(page_id),
        type('AttachmentTarget',(),{'attachment_name':uploaded.filename})())
    if not current or (current.attach_id,current.version)!=(uploaded.attach_id,uploaded.version):
        from plan_reconcile import PublishConflict
        raise PublishConflict('attachment_target_conflict')
    raw=client.download_attachment_version(page_id,uploaded.attach_id,uploaded.filename,uploaded.version)
    check=verify_attachment_bytes(raw,expected)
    if not check.ok:raise UploadVerificationConflict('exact attachment bytes mismatch')
    current=find_gantt_attachment(client.list_attachments(page_id),
        type('AttachmentTarget',(),{'attachment_name':uploaded.filename})())
    if not current or (current.attach_id,current.version)!=(uploaded.attach_id,uploaded.version):
        from plan_reconcile import PublishConflict
        raise PublishConflict('attachment_target_conflict')
    return check


def publish_prepared(client, preparation, *, allow_live_ab=False):
    """Reconcile each effect from fresh reads; confirm only the complete pipeline."""
    from copy import deepcopy
    from mofs_index.db import connect_durable
    from mofs_index.plan import query as q
    from plan_lock import target_lock
    from plan_operation import publication_journal, publish_event, PUBLISH_STAGES
    from plan_reconcile import (PublishConflict, PublishUnknown, reconcile_publish_page,
                                reconcile_publish_attachment)
    from plan_verify import managed_state
    from plan_receipt import validate_single_receipt, mask_secrets
    from macro import MacroInfo
    from prepared_plan import canonical_bytes
    from child_page import reconcile_created_child
    receipt=deepcopy(preparation.receipt)
    if receipt['exit_code'] or 'admitted' not in receipt['completed_stages']:
        return preparation
    context=preparation.context; operation=preparation.operation
    conn=connect_durable(context.db)
    stage=None
    def event(kind, data):
        return publish_event(conn,operation,context,kind,data)
    def completed(name, **details):
        nonlocal stage
        stage=name
        event('publish_stage',{'stage':name,**details})
        if name not in receipt['completed_stages']:
            receipt['completed_stages'].append(name)
    try:
        result=q.get_preparation_result(conn,operation.operation_id)
        prep=q.get_preparation(conn,operation.operation_id)
        if not result or result['result_id']!=preparation.result_id or result['state']!='admitted':
            raise ValueError('durable_admission_required')
        # Preserve uncertainty even if an archive/profile read fails before
        # remote reconciliation. Past network effects cannot become false.
        journal=publication_journal(conn,operation.operation_id)
        receipt['completed_stages']=list(dict.fromkeys(receipt['completed_stages']+journal['stages']))
        if q.publish_external_effect(conn,operation.operation_id):
            receipt.update(published=None,external_effect='unknown')
        request=prep['request']; parent_id=request['page_id']
        _guard_page(parent_id,allow_live_ab)
        binding=resolve_plan_binding(parent_id,request.get('project_slug'),lineage_id=request.get('lineage_id'),conn=conn)
        if binding['plan_id']!=q.get_operation(conn,operation.operation_id)['plan_id']:
            raise PublishConflict('operation_context_incomplete')
        slug=binding['project_slug'];receipt['project_slug']=slug
        if hasattr(client,'configure_transport'):
            client.configure_transport(context.settings)
        _load_publish_prepared(conn,prep)
        _publish_readback(conn,prep['snapshot_id'])
        raw=Path(plan_writer.verify_artifact(conn,result['representation_artifact_id'])).read_bytes()
        expected=hashlib.sha256(raw).hexdigest()
        admission=json.loads(Path(plan_writer.verify_artifact(conn,result['evidence_artifact_id'])).read_text())
        if admission['representation_sha256']!=expected or admission['admission']!=result['admission']:
            raise ValueError('admission_evidence_mismatch')
        # Persisted evidence fixes versions of all policies and profiles. Resume
        # does not re-convert with whichever defaults happen to be installed.
        for requirement in q.get_identity_requirements(conn,operation.operation_id):
            if requirement['preparation_revision']==prep['revision']:
                choice=plan_writer.select_operation_identity(conn,plan_writer.IdentityChoiceSpec(
                    operation.operation_id,requirement['requirement_id'],requirement['mapping_revision_id']))
                if choice['exit_code']:
                    raise PublishConflict('identity_confirmation_required')
        from urllib.parse import urlsplit
        namespace='confluence:'+urlsplit(context.settings['CONFLUENCE_URL']).netloc.lower()
        summary=result['result']['summary'];itogo=(summary['d1'],summary['d2'],summary['n_days'])
        saved=q.get_publish_confirmation(conn,operation.operation_id)
        journal=publication_journal(conn,operation.operation_id)
        network=journal['plan']
        for old_event in q.get_operation_events(conn,operation.operation_id):
            if old_event['event_kind']=='publish_network_result':
                old_receipt=json.loads(old_event['detail'])
                if old_receipt['verification']['schedule']['status']=='mismatch':
                    receipt=deepcopy(old_receipt)
                    raise ValueError('schedule_mismatch')
        lock_macro=(network or {}).get('macro',{}).get('macro_id')
        with ExitStack() as lock_scope:
            lock_scope.enter_context(target_lock(context.workvault,namespace,parent_id,lock_macro))
            if network is None:
                if q.publish_external_effect(conn,operation.operation_id):
                    # Old partial operations did not retain enough write intent.
                    raise PublishConflict('operation_context_incomplete')
                page,target=_current_target(client,parent_id)
                old=result['result']['target']
                if (target['managed']!=old.get('managed') or target['attachment']!=old['attachment']
                        or target['page_version']<old['page_version']):
                    raise PublishConflict()
                if request.get('child'):
                    macro_html=build_macro_html(*new_macro_ids());macro=find_macro(macro_html)
                    storage=build_itogo_html(*itogo,0)+macro_html
                    before=None
                else:
                    macro=find_macro(page['body']['storage']['value'])
                    macro_html=None if macro else build_macro_html(*new_macro_ids())
                    macro=macro or find_macro(macro_html)
                    storage=apply_itogo(page['body']['storage']['value']+(macro_html or ''),*itogo,0)
                    before=target['attachment']
                # A new preparation may correct its own old summary. It cannot
                # legitimize a third party's changed macro/summary/attachment.
                prior=q.latest_target_confirmation(conn,namespace,parent_id) if not request.get('child') else None
                if prior:
                    proof=json.loads(Path(plan_writer.verify_artifact(conn,prior['evidence_artifact_id'])).read_text())
                    if (target['managed']!=proof['final_managed'] or before is None
                            or (before['attach_id'],before['version'])!=(proof['attachment']['attachment_id'],proof['attachment']['attachment_version'])):
                        raise PublishConflict()
                    actual=client.download_attachment_version(parent_id,before['attach_id'],before['filename'],before['version'])
                    if hashlib.sha256(actual).hexdigest()!=proof['attachment']['actual_sha256']:
                        raise PublishConflict('attachment_target_conflict')
                before_sha=None
                if before:
                    before_sha=hashlib.sha256(client.download_attachment_version(parent_id,before['attach_id'],before['filename'],before['version'])).hexdigest()
                network={'result_id':result['result_id'],'representation_sha256':expected,'namespace':namespace,
                    'parent_id':parent_id,'child':bool(request.get('child')),'macro':asdict(macro),
                    'new_macro_html':macro_html,'base_managed':target['managed'],'base_version':target['page_version'],
                    'before_attachment':before,'before_attachment_sha256':before_sha,'intended_storage':storage,
                    'intended_managed':managed_state(storage),
                    'title':request.get('title') or default_child_title(page['title']),
                    'space_key':page['space']['key']}
                event('publish_network_plan',network)
            elif network['result_id']!=result['result_id'] or network['representation_sha256']!=expected or network['namespace']!=namespace:
                raise PublishConflict('operation_context_incomplete')
            macro=MacroInfo(**network['macro'])
            if macro._span is not None:
                macro._span=tuple(macro._span)
            receipt['verification'].update(attachment='not_verified',storage='not_verified')
            receipt['completed_stages']=list(dict.fromkeys(receipt['completed_stages']+journal['stages']))
            # Recover pessimistic external-effect state before performing reads.
            if journal['intents']:
                receipt.update(published=None,external_effect='unknown')
            page_id=parent_id
            if network['child']:
                parent=client.get_page(parent_id)
                reconcile_publish_page(parent,base_state=network['base_managed'],
                    intended_state=network['base_managed'],minimum_version=network['base_version'])
                created=journal['observations'].get('create')
                create_intent=journal['intents'].get('create')
                if created:
                    page=client.get_page(created['page_id'],expand='body.storage,version,space,ancestors')
                    if str(page['id'])!=created['page_id']:
                        raise PublishConflict('child_target_conflict')
                    if not page.get('ancestors') or str(page['ancestors'][-1]['id'])!=str(parent_id):
                        raise PublishConflict('child_target_conflict')
                elif create_intent:
                    page=reconcile_created_child(client,parent_id,network['title'],network['intended_storage'])
                else:
                    page=None
                if page is None:
                    # A complete parent/title lookup is mandatory on every retry.
                    count=(create_intent or {}).get('attempt',0)+1
                    if count>int(context.settings['HTTP_RETRY_LIMIT'])+1:
                        raise ValueError('page_create_retry_exhausted')
                    event('publish_network_intent',{'effect':'create','attempt':count,'parent_id':parent_id,
                        'title':network['title'],'storage_sha256':hashlib.sha256(network['intended_storage'].encode()).hexdigest()})
                    receipt.update(published=None,external_effect='unknown')
                    preparation.counters['POST']+=1
                    try:
                        page=client.create_page(network['title'],network['space_key'],network['intended_storage'],parent_id)
                    except Exception:
                        page=reconcile_created_child(client,parent_id,network['title'],network['intended_storage'])
                        if page is None:
                            raise PublishUnknown()
                    receipt['external_effect']='storage_written'
                    event('publish_observation',{'effect':'create','page_id':str(page['id']),'version':page['version']['number']})
                page_id=str(page['id']);receipt.update(published=None,external_effect='storage_written')
                base_state=network['intended_managed'];minimum_version=1
            else:
                base_state=network['base_managed'];minimum_version=network['base_version']
            _guard_page(page_id,allow_live_ab)
            if page_id!=parent_id:
                lock_scope.enter_context(target_lock(context.workvault,namespace,page_id,macro.macro_id))
            receipt.update(page_id=page_id,page_url=page_url(page_id))
            # A previously confirmed operation is read-only. Never repair it.
            if saved:
                proof=json.loads(Path(plan_writer.verify_artifact(conn,saved['evidence_artifact_id'])).read_text())
                current=client.get_page(page_id)
                if str(current['id'])!=page_id or managed_state(current['body']['storage']['value'])!=proof['final_managed']:
                    raise PublishConflict()
                recorded=proof['attachment']
                uploaded=AttachmentInfo(recorded['attachment_id'],network['macro']['attachment_name'],
                    recorded['attachment_version'],network['macro']['attachment_name'])
                verified=_verify_stage09_attachment(client,page_id,uploaded,expected)
                if not getattr(verified,'ok',False):
                    raise PublishConflict('attachment_target_conflict')
                receipt=deepcopy(saved['receipt']);receipt.update(status='unchanged',external_effect='none')
                event('publish_network_result',receipt)
                write_receipt(operation.operation_id,'publish',receipt,workvault=context.workvault)
                preparation.receipt=receipt
                return preparation
            page=client.get_page(page_id)
            if str(page['id'])!=page_id:
                raise PublishConflict()
            put_intent=journal['intents'].get('put')
            reconcile_publish_page(page,base_state=base_state,intended_state=network['intended_managed'],
                minimum_version=minimum_version,allow_written=bool(put_intent))
            upload_observation=journal['observations'].get('upload')
            uploaded,matches=reconcile_publish_attachment(client,page_id,macro,network['before_attachment'],expected,
                intent=journal['intents'].get('upload'),observed=upload_observation['attachment'] if upload_observation else None)
            if not matches:
                # With the same ID/version, an unexpected change of immutable
                # bytes is a conflict too; do not overwrite that evidence.
                if uploaded and network['before_attachment_sha256']:
                    current=client.download_attachment_version(page_id,uploaded.attach_id,uploaded.filename,uploaded.version)
                    if hashlib.sha256(current).hexdigest()!=network['before_attachment_sha256']:
                        raise PublishConflict('attachment_target_conflict')
                count=(journal['intents'].get('upload') or {}).get('attempt',0)+1
                if count>int(context.settings['HTTP_RETRY_LIMIT'])+1:
                    raise ValueError('attachment_retry_exhausted')
                event('publish_network_intent',{'effect':'upload','attempt':count,'page_id':page_id,
                    'before':asdict(uploaded) if uploaded else None,'expected_sha256':expected})
                receipt.update(published=None,external_effect='unknown')
                preparation.counters['POST']+=1
                try:
                    uploaded=_upload_prepared_bytes(client,page_id,macro.attachment_name,raw,uploaded)
                except Exception:
                    uploaded,matches=reconcile_publish_attachment(client,page_id,macro,network['before_attachment'],expected,intent=True)
                    if not matches:
                        raise PublishUnknown()
                receipt.update(published=None,external_effect='attachment_written' if not network['child'] else 'storage_written')
                event('publish_observation',{'effect':'upload','attachment':asdict(uploaded)})
            elif journal['intents'].get('upload'):
                receipt.update(published=None,external_effect='attachment_written' if not network['child'] else 'storage_written')
                if not upload_observation:
                    event('publish_observation',{'effect':'upload','attachment':asdict(uploaded),'reconciled':True})
            receipt['attachment_version']=uploaded.version
            completed('attachment_uploaded',attachment=asdict(uploaded),reused=matches)
            stage='attachment_verify'
            verified=_verify_stage09_attachment(client,page_id,uploaded,expected)
            if not getattr(verified,'ok',False) or verified.actual_sha256!=expected:
                raise UploadVerificationConflict('exact attachment verification returned false')
            receipt['verification']['attachment']='verified'
            completed('attachment_verified',attachment=asdict(uploaded),sha256=expected)
            # GET again even after an apparently successful POST. Each PUT uses
            # a new addressable patch; a 409 never enables an override.
            writes=(journal['intents'].get('put') or {}).get('attempt',0);did_put=False
            while True:
                page=client.get_page(page_id)
                if str(page['id'])!=page_id:
                    raise PublishConflict()
                state=reconcile_publish_page(page,base_state=base_state,intended_state=network['intended_managed'],
                    minimum_version=minimum_version,allow_written=bool(put_intent))
                verified=_verify_stage09_attachment(client,page_id,uploaded,expected)
                if not getattr(verified,'ok',False) or verified.actual_sha256!=expected:
                    raise UploadVerificationConflict('current attachment verification returned false')
                storage=page['body']['storage']['value']
                desired=apply_itogo(storage+(network['new_macro_html'] or '' if find_macro(storage) is None else ''),*itogo,0)
                if managed_state(storage)==network['intended_managed']:
                    # Already matches, including PUT with a lost local event.
                    if put_intent:
                        receipt.update(published=None,external_effect='storage_written')
                    completed('storage_written',page_version=page['version']['number'],reconciled=True)
                    break
                if state=='written':
                    raise PublishConflict()
                writes+=1
                if writes>int(context.settings['HTTP_RETRY_LIMIT'])+1:
                    raise ValueError('storage_retry_exhausted')
                put_intent={'effect':'put','attempt':writes,'page_id':page_id,'version':int(page['version']['number'])+1,
                    'before_version':int(page['version']['number']),'before_storage_sha256':hashlib.sha256(storage.encode()).hexdigest(),
                    'storage':desired,'storage_sha256':hashlib.sha256(desired.encode()).hexdigest()}
                event('publish_network_intent',put_intent)
                receipt.update(published=None,external_effect='unknown');preparation.counters['PUT']+=1
                try:
                    client.put_page(page_id,page['title'],desired,put_intent['version'])
                except ConfluenceError as exc:
                    if exc.status!=409:
                        # Resolve every uncertain transport response by reading.
                        observed=client.get_page(page_id)
                        outcome=reconcile_publish_page(observed,base_state=base_state,
                            intended_state=network['intended_managed'],minimum_version=put_intent['before_version'],allow_written=True)
                        if outcome!='written':
                            raise PublishUnknown()
                    else:
                        # Next iteration first checks fresh managed state AND
                        # current attachment, then rebuilds the patch.
                        continue
                except Exception:
                    observed=client.get_page(page_id)
                    outcome=reconcile_publish_page(observed,base_state=base_state,intended_state=network['intended_managed'],
                        minimum_version=put_intent['before_version'],allow_written=True)
                    if outcome!='written':
                        raise PublishUnknown()
                receipt.update(published=None,external_effect='storage_written');did_put=True
                event('publish_observation',{'effect':'put','page_id':page_id,'version':put_intent['version']})
                completed('storage_written',page_version=put_intent['version'])
                break
            stage='storage_verify'
            observed=client.get_page(page_id)
            if str(observed['id'])!=page_id:
                raise PublishConflict()
            observed_storage=observed['body']['storage']['value'];version=int(observed['version']['number'])
            if managed_state(observed_storage)!=network['intended_managed']:
                raise PublishConflict()
            expected_storage=put_intent['storage'] if did_put else observed_storage
            expected_version=put_intent['version'] if did_put else version
            check=verify_storage_observation(observed_storage,expected_storage=expected_storage,expected_macro=macro,
                expected_itogo=itogo,expected_version=expected_version,actual_version=version)
            if not check.ok:
                raise PublicationVerificationError('storage read-back failed')
            verified=_verify_stage09_attachment(client,page_id,uploaded,expected)
            if not getattr(verified,'ok',False) or verified.actual_sha256!=expected:
                raise UploadVerificationConflict('current attachment verification returned false')
            receipt['verification']['storage']='verified'
            completed('storage_verified',page_version=version,storage_sha256=hashlib.sha256(observed_storage.encode()).hexdigest())
            # Optional actual plugin observation is a separate source, never a
            # local schedule model disguised as the installed plugin.
            schedule=_observe_publish_schedule(client,page_id,admission,receipt['verification']['schedule'])
            receipt['verification']['schedule']=schedule
            if schedule['status']=='mismatch':
                raise ValueError('schedule_mismatch')
            attachment={'attachment_id':uploaded.attach_id,'attachment_version':uploaded.version,
                'expected_sha256':expected,'actual_sha256':verified.actual_sha256}
            storage_artifact,storage_sha=store_artifact(observed_storage.encode(),'storage_snapshot',ext='html',
                project_slug=slug,conn=conn,workvault=context.workvault)
            proof={'operation_id':operation.operation_id,'result_id':result['result_id'],'snapshot_id':prep['snapshot_id'],
                'admission_evidence_id':result['evidence_artifact_id'],'profiles':admission['profiles'],
                'diagnostics':admission['diagnostics'],'schedule':schedule,'attachment':attachment,'checks':check.checks,
                'page_id':page_id,'page_version':version,'storage_sha256':storage_sha,'final_managed':managed_state(observed_storage),
                'macro_id':macro.macro_id,'filename':macro.attachment_name}
            proof_artifact,_=store_artifact(canonical_bytes(proof),'publication_evidence',ext='json',
                project_slug=slug,conn=conn,workvault=context.workvault)
            observation=plan_writer.PageObservationSpec(plan_id=binding['plan_id'],page_id=page_id,page_version=version,
                storage_artifact_id=storage_artifact,itogo_raw=observed_storage,itogo_d1=itogo[0],itogo_d2=itogo[1],itogo_n=itogo[2],
                quality='ok',verification_status='verified_observation',verification_scope='current_state',
                verification_profile='publish-v1',verification={'checks':check.checks,'attachment':attachment},storage_sha256=storage_sha)
            unchanged=receipt['external_effect']=='none'
            receipt.update(status='unchanged' if unchanged else 'published_with_warnings' if receipt['warnings'] or schedule['status']=='not_verified' else 'published',
                published=True,exit_code=0,error=None)
            receipt['completed_stages']=list(PUBLISH_STAGES)
            validate_single_receipt(receipt)
            plan_writer.confirm_publish(conn,plan_writer.PublishConfirmationSpec(operation.operation_id,operation.attempt_id,
                result['result_id'],namespace,uploaded.attach_id,uploaded.version,macro.macro_id,macro.attachment_name,
                proof_artifact,observation,receipt))
            # SQL confirmation is authoritative. A failed mirror remains an
            # explicit failure for this invocation; resume repairs it by GET.
            stage='receipt_mirror'
            write_receipt(operation.operation_id,'publish',receipt,workvault=context.workvault)
    except Exception as exc:
        code=getattr(exc,'code',None) or ('attachment_verification_failed' if isinstance(exc,UploadVerificationConflict) else
            'storage_verification_failed' if isinstance(exc,PublicationVerificationError) else str(exc) if isinstance(exc,ValueError) else 'publication_failed')
        rc=getattr(exc,'exit_code',5)
        if isinstance(exc,ValueError) and (str(exc)=='target_conflict' or str(exc).startswith(('ambiguous Gantt','unbalanced structured-macro',
                'unclosed structured-macro','incomplete Gantt','malformed Gantt','duplicate Gantt'))):
            code='target_conflict';rc=4
        if receipt['external_effect']!='none' or receipt['published'] is True:
            receipt['published']=None
        receipt['completed_stages']=[s for s in receipt['completed_stages'] if s!='confirmed']
        _publish_error(receipt,code,rc)
        from urllib.error import URLError
        if isinstance(exc,PublishUnknown) or (isinstance(exc,(TimeoutError,URLError,ConnectionError)) and receipt['external_effect']!='none'):
            receipt['status']='unknown'
        if stage=='attachment_verify':receipt['verification']['attachment']='failed'
        if stage=='storage_verify':receipt['verification']['storage']='failed'
        receipt['error']['retryable']=rc!=4
        if code=='schedule_mismatch':
            receipt['error'].update(retryable=False,next_action='Разобрать наблюдение расписания; новая подготовка после адресного решения, без rollback')
        elif rc==4:
            receipt['error']['next_action']='Проверить конфликт цели; новая операция diff --project-slug '+str(receipt['project_slug'])
        else:
            receipt['error']['next_action']='Восстановить доступ к архиву/журналу/Confluence и выполнить resume --operation-id '+operation.operation_id
        try:
            event('publish_network_error',{'exception_type':type(exc).__name__,'http_status':getattr(exc,'status',None),
                'errno':getattr(exc,'errno',None),'stage':stage})
            event('publish_network_result',receipt)
            write_receipt(operation.operation_id,'publish-failed',receipt,workvault=context.workvault)
        except Exception:
            # A logging failure must never replace an error with false success.
            receipt['error']['next_action']='Восстановить журнал/зеркало и выполнить resume; исход сетевых записей проверить чтением'
    finally:
        conn.close()
    preparation.receipt=mask_secrets(receipt)
    return preparation


def _observe_publish_schedule(client,page_id,admission,saved_schedule):
    """No observation available is honest not_verified; never promote by bytes."""
    from copy import deepcopy
    schedule=deepcopy(saved_schedule)
    observer=getattr(client,'observe_plan_schedule',None)
    if observer is not None:
        observation=observer(page_id,admission)
        if observation:
            schedule['checks'].append(observation)
            if observation.get('status')=='mismatch':
                schedule['status']='mismatch'
    return schedule


def publish_plan(client=None, **kwargs):
    preparation=prepare_publish(client,**kwargs)
    if preparation.exit_code:return preparation
    return publish_prepared(client or ConfluenceClient(),preparation,allow_live_ab=kwargs.get('allow_live_ab',False))


def apply_plan(client, page_id, mpp_path, confirm, *, project_slug=None, timezone_hint=None,
               allow_live_ab=False, drop_links=None, **paths):
    """Compatible confirmed command; archive/admission are mandatory."""
    if not is_confirmed(confirm):
        raise PermissionError('Запись без подтверждения «лей»/«пиши»/«да» запрещена')
    return publish_plan(client,page_id=page_id,mpp_path=mpp_path,project_slug=project_slug,
        timezone_hint=timezone_hint,allow_live_ab=allow_live_ab,drop_links=drop_links,**paths)
