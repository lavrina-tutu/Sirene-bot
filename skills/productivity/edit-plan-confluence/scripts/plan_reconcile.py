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
    row = c.execute(
        "SELECT attempt_id, plan_id, lineage_id, prepared_sha256 "
        "FROM plan_import_attempt WHERE attempt_id = ?",
        (attempt_id,),
    ).fetchone()
    if not row:
        return None
    return {"attempt_id": row[0], "plan_id": row[1], "lineage_id": row[2], "prepared_sha256": row[3]}


def _lineage_page_id(c: sqlite3.Connection, lineage_id: str | None) -> str | None:
    if not lineage_id:
        return None
    row = c.execute("SELECT page_id FROM plan_lineage WHERE lineage_id = ?", (lineage_id,)).fetchone()
    return row[0] if row else None


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
