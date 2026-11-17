"""Квитанции шагов попытки — файловое зеркало ``plan_attempt_event`` (P1.W1.3).

Маскирует ``CONFLUENCE_TOKEN``/``Authorization`` при сериализации (R-022,
AC-123). Квитанции пишутся до и после каждого сетевого эффекта.
"""
from __future__ import annotations

import os
import tempfile
import json
import re
from pathlib import Path
from typing import Any

from env import get_workvault_path

_SECRET_KEY_RE = re.compile(r"(token|authorization|bearer)", re.IGNORECASE)
_BEARER_VALUE_RE = re.compile(r"(Bearer|Basic)\s+[A-Za-z0-9._~+/=\-]+", re.IGNORECASE)
_SECRET_VALUE_RE = re.compile(r"((?:[A-Za-z_]*token|authorization)\s*[=:]\s*)[^\s,;]+", re.IGNORECASE)


def _mask_value(value: Any) -> Any:
    if isinstance(value, str):
        return _SECRET_VALUE_RE.sub(r"\1***MASKED***", _BEARER_VALUE_RE.sub(lambda m: m.group(1) + " ***MASKED***", value))
    return value


def mask_secrets(payload: Any) -> Any:
    """Рекурсивно маскировать значения по ключам, похожим на токен/заголовок
    авторизации, и строки вида ``Bearer <token>`` в произвольном месте."""
    if isinstance(payload, dict):
        out: dict[str, Any] = {}
        for k, v in payload.items():
            if _SECRET_KEY_RE.search(str(k)):
                out[k] = "***MASKED***"
            else:
                out[k] = mask_secrets(v)
        return out
    if isinstance(payload, list):
        return [mask_secrets(v) for v in payload]
    return _mask_value(payload)


def receipts_dir(attempt_id: str, *, workvault: Path | None = None) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", attempt_id) or ".." in attempt_id:
        raise ValueError("invalid_receipt_id")
    return (Path(workvault) if workvault is not None else get_workvault_path()) / "_plan-receipts" / attempt_id


def write_receipt(attempt_id: str, event_id: str, payload: dict[str, Any], *, workvault: Path | None = None) -> Path:
    """Записать квитанцию ``receipts/<attempt-id>/<event-id>.json``, маскируя
    секреты. Идемпотентна: повторный вызов перезаписывает тем же содержимым
    (не накапливает дубликаты файлов)."""
    masked = mask_secrets(payload)
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", event_id) or ".." in event_id:
        raise ValueError("invalid_receipt_event_id")
    d = receipts_dir(attempt_id, workvault=workvault)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{event_id}.json"
    # A crash must not turn a receipt into truncated JSON.
    fd, temporary = tempfile.mkstemp(prefix=".receipt-", dir=d)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(masked, stream, ensure_ascii=False, indent=2, default=str)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        from mpp_input import _sync_dir
        _sync_dir(d)
        if json.loads(path.read_text(encoding="utf-8")) != json.loads(json.dumps(masked, default=str)):
            raise OSError("receipt_readback_failed")
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return path


def read_receipt(attempt_id: str, event_id: str, *, workvault: Path | None = None) -> dict[str, Any] | None:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", event_id) or ".." in event_id:
        raise ValueError("invalid_receipt_event_id")
    path = receipts_dir(attempt_id, workvault=workvault) / f"{event_id}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def single_receipt(*, operation_id=None, item_id=None, project_slug=None, source=None):
    """All §20.3.12.1 fields, including unknown nullable values."""
    return {"schema_version": 1, "operation_id": operation_id, "item_id": item_id,
            "status": "failed", "mode": "save", "exit_code": 5, "project_slug": project_slug,
            "source": source or {"name": None, "sha256": None, "size_bytes": None},
            "snapshot_id": None, "page_id": None, "page_url": None,
            "task_count": None, "display_task_count": None, "dependency_count": None,
            "exceptions": [], "attachment_version": None,
            "verification": {"archive": "not_verified", "attachment": "not_applicable", "storage": "not_applicable",
                             "source_values": {"status": "not_applicable", "checks": [], "limitations": [], "evidence_ids": []},
                             "schedule": {"status": "not_verified", "checks": [], "limitations": [], "evidence_ids": []}},
            "published": False, "warnings": [], "completed_stages": [], "external_effect": "none", "error": None}


def validate_single_receipt(payload):
    import jsonschema
    schema = Path(__file__).resolve().parents[1] / "references/schemas/single-receipt.schema.json"
    jsonschema.validate(payload, json.loads(schema.read_text()))
    if payload['mode'] == 'publish':
        if payload['status'] in ('published','published_with_warnings','unchanged'):
            if (payload['published'] is not True or payload['exit_code'] != 0
                    or any(payload['verification'][k] != 'verified' for k in ('archive','attachment','storage'))):
                raise ValueError('published receipt requires complete read-back')
        elif payload['published'] is True:
            raise ValueError('unconfirmed operation cannot claim published')
        if payload['external_effect'] != 'none' and payload['published'] is False:
            raise ValueError('unconfirmed external effect requires published:null')


def batch_counts(items):
    counts = dict.fromkeys(("total", "saved", "saved_with_warnings", "unchanged", "failed", "needs_decision", "not_started"), 0)
    for item in items:
        status = item["status"]
        counts["total"] += 1
        counts["saved" if status == "saved_with_warnings" else status] += 1
        if status == "saved_with_warnings":
            counts["saved_with_warnings"] += 1
    return counts


def batch_exit_code(counts, *, argument_error=False, conflict=False, infrastructure=False):
    if argument_error:
        return 2
    if conflict:
        return 4
    if infrastructure:
        return 5
    return 6 if any(counts[k] for k in ("failed", "needs_decision", "not_started")) else 0


def batch_receipt(*, batch_id=None, manifest_sha256=None, inputs_frozen_at=None, on_error="continue",
                  items=(), status=None, error=None, argument_error=False, conflict=False, infrastructure=False):
    counts = batch_counts(items)
    code = batch_exit_code(counts, argument_error=argument_error, conflict=conflict, infrastructure=infrastructure)
    status = status or ({2: "failed", 4: "conflict", 5: "infrastructure_stopped", 6: "completed_with_errors", 0: "completed"}[code])
    return {"schema_version": 1, "batch_id": batch_id, "mode": "batch_save", "status": status,
            "exit_code": code, "manifest_sha256": manifest_sha256, "inputs_frozen_at": inputs_frozen_at,
            "on_error": on_error, "counts": counts, "items": list(items), "published": False, "error": error}


def validate_batch_receipt(payload):
    import jsonschema
    schema = Path(__file__).resolve().parents[1] / "references/schemas/batch-receipt.schema.json"
    jsonschema.validate(payload, json.loads(schema.read_text()))
    if payload["counts"] != batch_counts(payload["items"]):
        raise ValueError("batch_counts_mismatch")


def write_failure_receipt(attempt_id: str, stage: str, error: Exception, *, external_effect: str) -> Path:
    """Unknown/partial remote writes never become published:false or success."""
    return write_receipt(attempt_id, "failure-" + stage, {
        "stage": stage, "status": "failed", "published": None,
        "external_effect": external_effect, "error": str(error),
        "schedule": "not_verified",
    })
