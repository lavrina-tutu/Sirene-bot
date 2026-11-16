"""Sequential archive batches over the common frozen save contract.

SQL is owned by MofsIndex. The immutable manifest and effective context live in
its existing batch/operation records; receipts are rebuildable file mirrors.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import uuid
from dataclasses import replace
from pathlib import Path

from env import Settings, select_mpxj_python
from mpp_input import InputError
from plan_archive import PlanBindingError, resolve_plan_binding
from plan_context import PlanContext, PROFILES
from plan_lock import batch_lock, PlanLockBusy
from plan_manifest import (ManifestError, absolute_path, canonical_json, canonicalize_request,
                           load_manifest, manifest_hash, scan_inbox, validate_manifest)
from plan_operation import ImportOperation, freeze_operation_input
from plan_receipt import batch_receipt, mask_secrets, validate_batch_receipt, write_receipt
from plan_reconcile import frozen_batch_input, reconcile_batch_item, saved_operation_receipt
from plan_save import save_frozen_input
from mofs_index.db import DEFAULT_DB_PATH, connect_durable
from mofs_index.plan import query as q, writer as w
from mofs_index.plan.migrate import ensure_plan_schema


SUCCESS = {"saved", "saved_with_warnings", "unchanged"}
LOCAL_ERRORS = {"mpp_unreadable", "invalid_reader_export", "invalid_snapshot", "mpp_read_timeout",
                "source_hash_mismatch", "binding_conflict", "project_slug_required", "invalid_project_slug_or_plan_key"}


class BatchError(RuntimeError):
    def __init__(self, code, *, exit_code=5, retryable=True):
        self.code, self.exit_code, self.retryable = code, exit_code, retryable
        super().__init__(code)


def _error(code, *, retryable=False, batch_id=None):
    return {"code": code, "message": "Пакет: " + code, "retryable": retryable,
            "next_action": ("batch resume --batch-id " + batch_id) if retryable and batch_id else
                           "Создать новый пакет" if code in ("inputs_not_frozen", "batch_manifest_conflict", "batch_context_conflict") else None}


def _failure(exc, *, batch_id=None, receipt=None):
    code = getattr(exc, "code", "archive_unavailable")
    exit_code = 2 if isinstance(exc, ManifestError) else 4 if isinstance(exc, PlanLockBusy) else getattr(exc, "exit_code", 5)
    if isinstance(exc, (w.PlanWriterError, q.PlanQueryError)):
        code = str(exc).split(":")[0]
        exit_code = 4 if code in ("batch_manifest_conflict", "inputs_not_frozen", "batch_not_found") else 5
    error = _error(code, retryable=exit_code == 5, batch_id=batch_id)
    base = receipt or batch_receipt(batch_id=batch_id)
    return batch_receipt(batch_id=base["batch_id"], manifest_sha256=base["manifest_sha256"],
        inputs_frozen_at=base["inputs_frozen_at"], on_error=base["on_error"], items=base["items"],
        error=error, argument_error=exit_code == 2, conflict=exit_code == 4, infrastructure=exit_code == 5)


def _db(context=None, db_path=None):
    return Path(db_path or (context.db if context else DEFAULT_DB_PATH)).expanduser().resolve()


def _connect(database):
    conn = connect_durable(database)
    ensure_plan_schema(conn)
    return conn


def _check_paths(snapshot, *, context=None, workvault=None, cache_dir=None):
    paths = snapshot["paths"]
    for name, value in (("db", context.db if context else None),
                        ("workvault", context.workvault if context else workvault),
                        ("cache_dir", context.cache_dir if context else cache_dir)):
        if value is not None and str(Path(value).expanduser().resolve()) != paths[name]:
            raise BatchError("batch_context_conflict", exit_code=4)


def _document(*, mpp=None, manifest=None, inbox=None, project_slug=None, lineage_id=None, timezone_hint=None):
    if sum(bool(value) for value in (mpp, manifest, inbox)) != 1:
        raise ManifestError("mutually_exclusive_inputs")
    if manifest:
        if any(value is not None for value in (project_slug, lineage_id, timezone_hint)):
            raise ManifestError("manifest_common_context_forbidden")
        return load_manifest(manifest), Path(absolute_path(manifest)).parent, {"kind": "manifest"}, []
    if not project_slug:
        raise ManifestError("project_slug_required")
    paths, diagnostics = scan_inbox(inbox) if inbox else (mpp, [])
    optional = {key: value for key, value in (("lineage_id", lineage_id), ("timezone_hint", timezone_hint)) if value is not None}
    document = {"schema_version": 1, "items": [{"item_id": str(i), "path": str(path),
                 "project_slug": project_slug, **optional} for i, path in enumerate(paths, 1)]}
    validate_manifest(document)
    source = {"kind": "inbox", "path": absolute_path(inbox)} if inbox else {"kind": "mpp"}
    return document, None, source, diagnostics


def _code_fingerprints(context):
    # Pin reader code as well as runtime/profile versions, without duplicating it.
    return {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (context.mpp_reader / "plan_export.py", context.mpp_reader / "read_mpp.py")}


def _effective_context(context):
    try:
        runtime = select_mpxj_python(settings=Settings(context.settings, context.sources))
    except RuntimeError as exc:
        raise BatchError("mpxj_runtime_unavailable") from exc
    return replace(context, settings={**context.settings, "MPXJ_PYTHON": runtime.python}), runtime.versions


def _project_defaults(conn, document, context):
    defaults = {}
    for item in document["items"]:
        lineage = item.get("lineage_id")
        if lineage is None:
            # An explicit foreign lineage remains an item error during save.
            lineage = resolve_plan_binding(None, item["project_slug"], conn=conn)["lineage_id"]
        defaults[item["item_id"]] = {"lineage_id": lineage, "timezone_hint": item.get("timezone_hint"),
                                    "normalization": context.snapshot()["profiles"]["NORMALIZATION_PROFILE"]}
    return defaults


def _compact(row, result=None):
    status = (result or {}).get("status", row["status"])
    if status not in SUCCESS | {"failed", "needs_decision"}:
        status = "not_started"
    if result is None:
        # A freeze error or an unverified SQL commit is processed in order;
        # stop leaves later items not_started with known intake diagnostics.
        status = "not_started"
    error = (result or {}).get("error")
    if error is None and row["error_code"]:
        error = _error(row["error_code"], retryable=bool(row["retryable"]))
    return {"item_id": json.loads(row["transport_json"])["manifest_item_id"], "position": row["ordinal"],
            "status": status, "operation_id": row["operation_id"], "snapshot_id": row["snapshot_id"],
            "sha256": row["source_mpp_sha256"], "receipt_ref": (result or {}).get("receipt_ref"),
            "error": error, "warnings": (result or {}).get("warnings", [])}


def _current(conn, batch_id, state=None):
    batch = state["batch"] if state else q.get_import_batch(conn, batch_id)
    if not batch:
        raise BatchError("batch_not_found", exit_code=4)
    rows = state["items"] if state else q.get_batch_items(conn, batch_id)
    items = [_compact(row, state["results"][row["operation_id"]] if state else q.get_batch_item_result(conn, row["operation_id"])) for row in rows]
    reason = json.loads(batch["stop_reason"]) if batch["stop_reason"] else None
    infrastructure = batch["status"] == "infrastructure_stopped"
    if batch["inputs_frozen_at"] is None:
        return batch_receipt(batch_id=batch_id, manifest_sha256=batch["manifest_sha256"], on_error=batch["on_error"],
                             items=items, conflict=True, error=_error("inputs_not_frozen"))
    return batch_receipt(batch_id=batch_id, manifest_sha256=batch["manifest_sha256"], inputs_frozen_at=batch["inputs_frozen_at"],
                         on_error=batch["on_error"], items=items, infrastructure=infrastructure,
                         status=batch["status"] if batch["status"] in ("stopped", "infrastructure_stopped") else None, error=reason)


def _record_result(conn, row, attempt_id, result, context):
    receipt = result.to_dict() if hasattr(result, "to_dict") else result
    if hasattr(result, "to_dict") and receipt.get("error") and receipt["error"]["code"] not in LOCAL_ERRORS:
        # Infrastructure repair can retry on the identical frozen context. This
        # changes only the batch retry classification, never the snapshot/link.
        receipt["error"] = {**receipt["error"], "retryable": True}
    compact = _compact(row, receipt)
    compact["status"] = receipt["status"] if receipt["status"] in SUCCESS | {"needs_decision"} else "failed"
    compact["snapshot_id"] = receipt.get("snapshot_id") or row["snapshot_id"]
    compact["receipt_ref"] = str(Path("_plan-receipts") / row["operation_id"] / "save.json") if receipt["exit_code"] == 0 else None
    w.finish_batch_item(conn, row["item_id"], attempt_id, canonical_json(compact))
    return compact


def freeze_batch_inputs(conn, batch_id, *, context):
    """Called under the batch lock; finish *all* inputs even for on_error:stop."""
    batch = q.get_import_batch(conn, batch_id)
    if batch["inputs_frozen_at"]:
        return
    manifest = json.loads(batch["manifest_json"])
    for row, request in zip(q.get_batch_items(conn, batch_id), manifest["items"]):
        attempt_id = w.begin_operation_attempt(conn, row["operation_id"], row["item_id"])
        operation = ImportOperation(row["operation_id"], row["item_id"], attempt_id)
        try:
            frozen = freeze_operation_input(conn, operation)
            if request.get("expected_sha256") and frozen.sha256 != request["expected_sha256"]:
                raise InputError("source_hash_mismatch")
        except InputError as exc:
            if exc.code.startswith("frozen_"):
                raise BatchError(exc.code) from exc
            w.fail_import_item(conn, row["item_id"], attempt_id, exc.code, retryable=False)
            row = q.get_import_item(conn, row["item_id"])
            w.record_operation_event(conn, attempt_id, "batch_input_error", detail=exc.code, status="failed")
            if exc.candidates:
                write_receipt(row["operation_id"], "input-error", {"code": exc.code, "candidates": list(exc.candidates)}, workvault=context.workvault)
    w.finalize_batch_freeze(conn, batch_id)


def _verify_execution(context, stored):
    profile = PROFILES / (context.settings["NORMALIZATION_PROFILE"] + ".json")
    expected = stored["execution"]["profiles"]["NORMALIZATION_PROFILE"]["sha256"]
    if not profile.is_file() or hashlib.sha256(profile.read_bytes()).hexdigest() != expected:
        raise BatchError("batch_context_conflict", exit_code=4)
    if _code_fingerprints(context) != stored["reader_code"]:
        raise BatchError("batch_context_conflict", exit_code=4)
    try:
        runtime = select_mpxj_python(settings=Settings(context.settings, context.sources))
    except RuntimeError as exc:
        raise BatchError("mpxj_runtime_unavailable") from exc
    if runtime.versions != stored["runtime_versions"] or runtime.python != context.settings["MPXJ_PYTHON"]:
        raise BatchError("batch_context_conflict", exit_code=4)


def _mirror_batch(conn, batch_id, context):
    receipt = _current(conn, batch_id)
    validate_batch_receipt(receipt)
    try:
        write_receipt(batch_id, "batch", receipt, workvault=context.workvault)
    except OSError:
        error = _error("receipt_mirror_failed", retryable=True, batch_id=batch_id)
        w.finish_import_batch(conn, batch_id, status="infrastructure_stopped", stop_reason=canonical_json(error))
        receipt = _current(conn, batch_id)
    return receipt


def _run_batch(conn, batch_id, *, context, retry_failed=False, tracker=None):
    batch = q.get_import_batch(conn, batch_id)
    if not batch["inputs_frozen_at"]:
        raise BatchError("inputs_not_frozen", exit_code=4)
    stored = json.loads(batch["context_json"])
    # Verify every accepted artifact before any processing. No original locator
    # is opened here, including when the input or the whole Inbox has vanished.
    for row in q.get_batch_items(conn, batch_id):
        if row["frozen_locator"]:
            frozen_batch_input(row)
    execution_checked = False
    for row in q.get_batch_items(conn, batch_id):
        previous = q.get_batch_item_result(conn, row["operation_id"])
        compact = _compact(row, previous)
        if row["snapshot_id"]:
            # A complete SQL result can restore its missing file mirror directly.
            saved = saved_operation_receipt(conn, row["operation_id"])
            if previous and compact["status"] in SUCCESS and saved and saved["exit_code"] == 0:
                mirror = context.workvault / "_plan-receipts" / row["operation_id"] / "save.json"
                try:
                    mirror_matches = json.loads(mirror.read_text(encoding="utf-8")) == saved
                except (OSError, ValueError):
                    mirror_matches = False
                if mirror_matches:
                    continue
            result = reconcile_batch_item(conn, row, context=context)
            attempt_id = q.get_operation_attempts(conn, row["operation_id"])[-1]["attempt_id"]
            compact = _record_result(conn, row, attempt_id, result, context)
        elif previous is None and row["status"] == "failed":
            attempt_id = q.get_operation_attempts(conn, row["operation_id"])[-1]["attempt_id"]
            compact = _record_result(conn, row, attempt_id, {"status": "failed", "exit_code": 5,
                "error": _error(row["error_code"]), "warnings": []}, context)
        elif compact["status"] == "needs_decision" or (compact["status"] == "failed" and
                (not row["frozen_locator"] or not retry_failed or not (compact["error"] or {}).get("retryable"))):
            pass
        else:
            if not execution_checked:
                _verify_execution(context, stored)
                execution_checked = True
            attempt_id = w.start_batch_item(conn, row["item_id"])
            operation = ImportOperation(row["operation_id"], row["item_id"], attempt_id)
            frozen = frozen_batch_input(row)
            result = save_frozen_input(frozen, sha256=frozen.sha256, context=context, operation=operation)
            compact = _record_result(conn, row, attempt_id, result, context)
        if tracker is not None:
            tracker["receipt"] = _current(conn, batch_id)
        if compact["status"] == "failed" and (compact["error"] or {}).get("code") not in LOCAL_ERRORS and row["frozen_locator"]:
            # Freeze errors are local, including ZIP limits and hash mismatch.
            # All unclassified execution/storage/journal errors stop the batch.
            if not any(e["event_kind"] == "batch_processing" for e in q.get_operation_events(conn, row["operation_id"])):
                infrastructure = False
            else:
                infrastructure = True
            if infrastructure:
                error = compact["error"] or _error("archive_unavailable", retryable=True, batch_id=batch_id)
                w.finish_import_batch(conn, batch_id, status="infrastructure_stopped", stop_reason=canonical_json(error))
                return _mirror_batch(conn, batch_id, context)
        if compact["status"] not in SUCCESS and batch["on_error"] == "stop":
            w.finish_import_batch(conn, batch_id, status="stopped", stop_reason=canonical_json(compact["error"]))
            return _mirror_batch(conn, batch_id, context)
    receipt = _current(conn, batch_id)
    status = "completed_with_errors" if any(receipt["counts"][k] for k in ("failed", "needs_decision", "not_started")) else "completed"
    w.finish_import_batch(conn, batch_id, status=status)
    return _mirror_batch(conn, batch_id, context)


def _locked_batch(database, batch_id, action):
    """Keep failure recording under the lock, including the SQL-unavailable path."""
    conn = None
    tracker = {}
    try:
        with batch_lock(database, batch_id):
            try:
                conn = _connect(database)
                return action(conn, tracker)
            except Exception as exc:
                receipt = tracker.get("receipt")
                if conn is not None:
                    try:
                        if q.get_import_batch(conn, batch_id):
                            receipt = _current(conn, batch_id)
                            if receipt["inputs_frozen_at"] and getattr(exc, "exit_code", 5) == 5:
                                w.finish_import_batch(conn, batch_id, status="infrastructure_stopped", stop_reason=canonical_json(
                                    _error(getattr(exc, "code", "archive_unavailable"), retryable=True, batch_id=batch_id)))
                                receipt = _current(conn, batch_id)
                    except (sqlite3.Error, w.PlanWriterError, q.PlanQueryError):
                        pass  # Preserve the last known successes if journaling itself failed.
                return mask_secrets(_failure(exc, batch_id=batch_id, receipt=receipt))
    except Exception as exc:
        return mask_secrets(_failure(exc, batch_id=batch_id))
    finally:
        if conn is not None:
            conn.close()


def create_batch(*, mpp=None, manifest=None, inbox=None, project_slug=None, lineage_id=None, timezone_hint=None,
                 batch_id=None, on_error=None, context=None, db_path=None, workvault=None, cache_dir=None):
    try:
        document, base, source, diagnostics = _document(mpp=mpp, manifest=manifest, inbox=inbox,
            project_slug=project_slug, lineage_id=lineage_id, timezone_hint=timezone_hint)
        # Canonical validation, including policy, precedes database/arrival writes.
        canonicalize_request(document, base_dir=base, on_error=on_error, source=source)
        batch_id = batch_id or "batch-" + uuid.uuid4().hex
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", batch_id) or ".." in batch_id:
            raise ManifestError("invalid_batch_id")
        database = _db(context, db_path)
        def action(conn, tracker):
            effective = context
            existing = q.get_import_batch(conn, batch_id)
            if existing:
                stored = json.loads(existing["context_json"])
                receipt = _current(conn, batch_id)
                _check_paths(stored["execution"], context=context, workvault=workvault, cache_dir=cache_dir)
                policy = on_error if on_error is not None else document.get("on_error", existing["on_error"])
                candidate = canonicalize_request(document, base_dir=base, on_error=policy, defaults=stored["defaults"], source=source)
                if manifest_hash(candidate) != existing["manifest_sha256"]:
                    raise BatchError("batch_manifest_conflict", exit_code=4)
                return receipt
            effective = effective or PlanContext.resolve(db=database, workvault=workvault, cache_dir=cache_dir)
            effective, runtime_versions = _effective_context(effective)
            defaults = _project_defaults(conn, document, effective)
            canonical = canonicalize_request(document, base_dir=base, on_error=on_error, defaults=defaults, source=source)
            stored = {"execution": effective.snapshot(), "defaults": defaults, "diagnostics": diagnostics,
                      "reader_code": _code_fingerprints(effective), "runtime_versions": runtime_versions}
            items = tuple(w.BatchItemSpec(item["item_id"], item["path"], canonical_json({**effective.snapshot(), "save": {
                key: item.get(key) for key in ("project_slug", "lineage_id", "timezone_hint", "source_version_date")}}),
                item.get("source_version_date")) for item in canonical["items"])
            w.create_batch_with_items(conn, w.ImportBatchSpec(batch_id, 1, canonical_json(canonical), manifest_hash(canonical),
                source["kind"], canonical_json(stored), canonical["on_error"]), items)
            tracker["receipt"] = _current(conn, batch_id)
            freeze_batch_inputs(conn, batch_id, context=effective)
            return _run_batch(conn, batch_id, context=effective, tracker=tracker)
        return _locked_batch(database, batch_id, action)
    except Exception as exc:
        return mask_secrets(_failure(exc, batch_id=batch_id))


def resume_batch(batch_id, *, retry_failed=False, context=None, db_path=None, workvault=None, cache_dir=None):
    def action(conn, tracker):
        tracker["receipt"] = _current(conn, batch_id)
        batch = q.get_import_batch(conn, batch_id)
        snapshot = json.loads(batch["context_json"])["execution"]
        _check_paths(snapshot, context=context, workvault=workvault, cache_dir=cache_dir)
        return _run_batch(conn, batch_id, context=PlanContext.from_snapshot(snapshot), retry_failed=retry_failed, tracker=tracker)
    return _locked_batch(_db(context, db_path), batch_id, action)


def run_batch(batch_id, **kwargs):
    """Process an already frozen batch under the same lock as resume."""
    return resume_batch(batch_id, **kwargs)


def show_batch(batch_id, *, view="all", context=None, db_path=None, workvault=None, cache_dir=None):
    conn = None
    try:
        conn = _connect(_db(context, db_path))
        # One SQLite read transaction keeps counts/results coherent during a run.
        # Transaction SQL remains in typed query API.
        state = q.read_batch_state(conn, batch_id)
        receipt, stored = _current(conn, batch_id, state), state["batch"]
        _check_paths(json.loads(stored["context_json"])["execution"], context=context, workvault=workvault, cache_dir=cache_dir)
        if view == "errors":
            return {"schema_version": 1, "action": "show_batch", "batch_id": batch_id, "view": view, "exit_code": 0,
                    "result": {**{key:receipt[key] for key in ("status", "exit_code", "counts", "error", "manifest_sha256", "inputs_frozen_at")},
                               "items": [item for item in receipt["items"] if item["status"] not in SUCCESS]},
                    "published": False, "error": None}
        if view != "all":
            raise ManifestError("invalid_batch_view")
        return receipt
    except Exception as exc:
        return mask_secrets(_failure(exc, batch_id=batch_id))
    finally:
        if conn is not None:
            conn.close()
