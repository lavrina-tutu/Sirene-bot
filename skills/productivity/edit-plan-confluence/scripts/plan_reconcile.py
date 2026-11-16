"""Reconcile неизвестного исхода попытки (timeout/потерянный ответ) — P1.W1.7.

Адресная сверка по ID/времени/hash, без слепого повтора (R-010, AC-106).
Ambiguity (несколько одинаково подходящих кандидатов) даёт ``unknown``, а
не придуманный ``confirmed``.
"""
from __future__ import annotations

import hashlib
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

MOFS_INDEX_ROOT = Path.home() / "USERTOOLS" / "MofsIndex"
if str(MOFS_INDEX_ROOT) not in sys.path:
    sys.path.insert(0, str(MOFS_INDEX_ROOT))

from mofs_index.plan import query as plan_query
from mofs_index.plan import writer as plan_writer  # noqa: E402

from plan_archive import _connect  # noqa: E402
from plan_receipt import write_receipt  # noqa: E402


@dataclass
class ReconcileOutcome:
    attempt_id: str
    status: str  # confirmed|unknown|failed|not_applicable
    reason: str
    attachment_id: str | None = None
    attachment_version: int | None = None


def _attempt_row(c: sqlite3.Connection, attempt_id: str) -> dict | None:
    return plan_query.get_attempt(c,attempt_id)


def _lineage_page_id(c: sqlite3.Connection, lineage_id: str | None) -> str | None:
    row=plan_query.get_lineage(c,lineage_id) if lineage_id else None
    return row["page_id"] if row else None


def reconcile_attempt(
    client,
    attempt_id: str,
    *,
    db_path: Path | None = None,
    conn: sqlite3.Connection | None = None,
) -> ReconcileOutcome:
    own_conn = conn is None
    c = conn or _connect(db_path)
    try:
        attempt = _attempt_row(c, attempt_id)
        if attempt is None:
            return ReconcileOutcome(attempt_id, "unknown", "attempt_id не найден в SQL")

        page_id = _lineage_page_id(c, attempt["lineage_id"])
        if not page_id:
            return ReconcileOutcome(attempt_id, "unknown", "нет привязки lineage -> page_id")

        expected_sha256 = attempt["prepared_sha256"]
        if not expected_sha256:
            return ReconcileOutcome(attempt_id, "unknown", "нет ожидаемого hash для сверки")

        attachments = client.list_attachments(page_id)
        candidates: list[tuple[str, int]] = []
        for att in attachments:
            version_info = att.get("version") or {}
            version = int(version_info.get("number", 1)) if isinstance(version_info, dict) else 1
            title = att.get("title")
            if not title:
                continue
            try:
                raw = client.download_attachment(page_id, title, version)
            except Exception:
                continue
            if hashlib.sha256(raw).hexdigest() == expected_sha256:
                candidates.append((str(att.get("id")), version))

        if len(candidates) == 1:
            attach_id, version = candidates[0]
            outcome = ReconcileOutcome(
                attempt_id, "unknown",
                "вложение найдено; storage/admission не проверены, вся операция не подтверждена",
                attachment_id=attach_id, attachment_version=version,
            )
        elif len(candidates) == 0:
            outcome = ReconcileOutcome(attempt_id, "unknown", "кандидат с ожидаемым hash не найден")
        else:
            outcome = ReconcileOutcome(
                attempt_id, "unknown",
                f"неоднозначно: {len(candidates)} кандидатов с совпадающим hash, evidence недостаточно",
            )

        event_id = plan_writer.record_event(
            c, attempt_id, "attachment_verify", "confirmed" if len(candidates) == 1 else "unknown",
            detail=outcome.reason,
        )
        write_receipt(attempt_id, event_id, {
            "stage": "attachment_verify",
            "status": "confirmed" if len(candidates) == 1 else "unknown",
            "operation_status": outcome.status, "published": None,
            "scope": "attachment_version", "external_effect": "partial" if candidates else "unknown",
            "reason": outcome.reason,
            "attachment_id": outcome.attachment_id,
            "attachment_version": outcome.attachment_version,
        })
        return outcome
    finally:
        if own_conn:
            c.close()


def reconcile_import(conn: sqlite3.Connection, item_id: str, *, receipt_writer=None) -> dict | None:
    """Committed link first, then archive read-back. No parser/reimport fallback.

    A read-back or mirror failure propagates with the committed IDs retained in
    MofsIndex. Callers must repair identical archived bytes and retry this read.
    """
    committed=plan_query.get_committed_import(conn,item_id)
    if committed is None:
        return None
    item,snapshot=committed["item"],committed["snapshot"]
    plan_writer.verify_snapshot(conn,item["snapshot_id"])
    if not snapshot:
        raise plan_writer.PlanWriterError("snapshot_missing")
    source=snapshot.get("source_json")
    expected=snapshot.get("normalized_data_sha256")
    if source is not None and hashlib.sha256(source.encode()).hexdigest() != expected:
        raise plan_writer.PlanWriterError("normalized_data_hash_mismatch")
    result={"operation_id":item["operation_id"],"item_id":item_id,"snapshot_id":item["snapshot_id"],
            "status":item["status"],"verification":{"archive":"verified"},"published":False,"external_effect":"none"}
    if receipt_writer:
        receipt_writer(result)
    return result


def saved_operation_receipt(conn, operation_id: str) -> dict | None:
    """Read the last full result from SQL, independently of its file mirror."""
    import json
    from plan_receipt import validate_single_receipt
    for event in reversed(plan_query.get_operation_events(conn, operation_id)):
        if event["event_kind"] in ("save_result", "receipt_mirror_failed"):
            result = json.loads(event["detail"])
            validate_single_receipt(result)
            return result
    return None


class PublishConflict(RuntimeError):
    exit_code = 4
    def __init__(self, code='target_conflict'):
        super().__init__(code)
        self.code = code


class PublishUnknown(RuntimeError):
    code = 'network_outcome_unknown'
    exit_code = 5


def reconcile_publish_attachment(client, page_id, macro, before, expected_sha256, *, intent=None, observed=None):
    """Fresh identity/version + exact bytes before deciding whether POST is safe.

    An unobserved POST can account for at most one version. A later version is
    a conflict even when it happens to contain the same bytes.
    """
    from dataclasses import asdict
    from gantt_attachment import find_gantt_attachment
    from plan_verify import verify_attachment_bytes
    current = find_gantt_attachment(client.list_attachments(page_id), macro)
    if observed:
        if not current or asdict(current) != observed:
            raise PublishConflict('attachment_target_conflict')
    elif current:
        same_before = before and (current.attach_id, current.version) == (before['attach_id'], before['version'])
        if not same_before:
            if not intent or (before and (current.attach_id != before['attach_id'] or current.version != before['version'] + 1)) or (not before and current.version != 1):
                raise PublishConflict('attachment_target_conflict')
    elif before or observed:
        raise PublishConflict('attachment_target_conflict')
    if not current:
        return None, False
    raw = client.download_attachment_version(page_id, current.attach_id, current.filename, current.version)
    matches = verify_attachment_bytes(raw, expected_sha256).ok
    if observed or (intent and (not before or current.version != before['version'])):
        if not matches:
            raise PublishConflict('attachment_target_conflict')
    return current, matches


def reconcile_publish_page(page, *, base_state, intended_state, minimum_version, allow_written=False):
    from plan_verify import managed_state
    current = managed_state(page['body']['storage']['value'])
    if int(page['version']['number']) < minimum_version:
        raise PublishConflict()
    if current == base_state:
        return 'before'
    if allow_written and current == intended_state:
        return 'written'
    raise PublishConflict()


def frozen_batch_input(item):
    """Verify registered frozen locators only. Never refreeze an original path."""
    from mpp_input import FrozenInput, InputError
    path = Path(item["frozen_locator"])
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size != item["size_bytes"] or hashlib.sha256(path.read_bytes()).hexdigest() != item["source_mpp_sha256"]:
            raise InputError("frozen_input_corrupt")
        if item["container_sha256"]:
            container = Path(item["container_locator"])
            if container.is_symlink() or not container.is_file() or hashlib.sha256(container.read_bytes()).hexdigest() != item["container_sha256"]:
                raise InputError("frozen_container_corrupt")
    except OSError as exc:
        raise InputError("frozen_input_corrupt") from exc
    return FrozenInput(path, item["source_mpp_sha256"], item["size_bytes"], item["original_name"],
                       item["original_locator"], item["frozen_at"], item["container_sha256"],
                       item["container_locator"], item["zip_member"])


def reconcile_batch_item(conn, item, *, context):
    """Resolve a committed processing item before any retry/reader.

    Reuse the common full read-back/receipt implementation and original attempt;
    even an interrupted mirror must not create a second arrival or snapshot.
    """
    from plan_operation import ImportOperation
    from plan_save import save_frozen_input
    committed = plan_query.get_committed_import(conn, item["item_id"])
    if not committed:
        return None
    attempts = plan_query.get_operation_attempts(conn, item["operation_id"])
    if not attempts:
        raise plan_writer.PlanWriterError("operation_attempt_missing")
    frozen = frozen_batch_input(item)
    operation = ImportOperation(item["operation_id"], item["item_id"], attempts[-1]["attempt_id"])
    return save_frozen_input(frozen, sha256=frozen.sha256, context=context, operation=operation)
