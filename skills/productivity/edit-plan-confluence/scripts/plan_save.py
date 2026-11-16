"""Single local save pipeline, shared with future frozen batch callers.

Only MofsIndex's typed API writes SQL. No network/client imports, publication or
baseline selection. File mirrors never replace the committed SQL history.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from jsonschema.exceptions import ValidationError as SchemaValidationError

from env import Settings, select_mpxj_python
from mpp_input import FrozenInput, InputError
from plan_archive import PlanBindingError, resolve_plan_binding, store_artifact
from plan_context import PlanContext, PROFILES
from plan_cache import ParseCache
from prepared_plan import NormalizationProfile, PreparedPlan, validate_export
from plan_receipt import mask_secrets, single_receipt, write_receipt
from plan_operation import ImportOperation, begin_import, freeze_operation_input, finish_archive_operation
from plan_reconcile import reconcile_import
from mofs_index.db import connect_durable
from mofs_index.plan import query as q, writer as w
from mofs_index.plan.ingest_mpp import build_snapshot_spec
from mofs_index.plan.migrate import ensure_plan_schema


class PlanSaveError(RuntimeError):
    def __init__(self, code, *, exit_code=5, retryable=False):
        self.code, self.exit_code, self.retryable = code, exit_code, retryable
        super().__init__(code)


@dataclass
class SaveResult:
    receipt: dict[str, Any]
    counters: dict[str, int | None] = field(default_factory=dict)
    plan_id: str | None = None
    lineage_id: str | None = None
    mpp_artifact_id: str | None = None
    export_artifact_id: str | None = None
    export_sha256: str | None = None

    def __getattr__(self, key):
        if key == "mpp_sha256":
            return self.receipt["source"]["sha256"]
        if key in self.receipt:
            return self.receipt[key]
        raise AttributeError(key)

    def to_dict(self):
        return json.loads(json.dumps(self.receipt))


def validate_save_arguments(*, timezone_hint=None, source_version_date=None):
    if timezone_hint is not None:
        try:
            ZoneInfo(timezone_hint)
        except (ValueError, KeyError, TypeError) as exc:
            raise PlanSaveError("invalid_timezone", exit_code=2) from exc
    if source_version_date is not None:
        try:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", source_version_date):
                raise ValueError()
            date.fromisoformat(source_version_date)
        except (TypeError, ValueError) as exc:
            raise PlanSaveError("invalid_source_version_date", exit_code=2) from exc


def run_export_full(mpp_path: Path, *, context: PlanContext, diagnostics_dir: Path,
                    runtime=None, timeout=None) -> dict[str, Any]:
    """The shared reader boundary: one read; stdout is diagnostics, JSON a file.

    Never echo driver exceptions or arbitrary output into the public receipt.
    """
    runtime = runtime or select_mpxj_python(settings=Settings(context.settings, context.sources))
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    output = diagnostics_dir / "reader-export.json"
    output.unlink(missing_ok=True)
    try:
        proc = subprocess.run([runtime.python, str(context.mpp_reader / "plan_export.py"), str(mpp_path),
                               "--out", str(output)], capture_output=True, text=True,
                              timeout=timeout or context.settings["MPP_READ_TIMEOUT_SECONDS"])
    except subprocess.TimeoutExpired as exc:
        raise PlanSaveError("mpp_read_timeout", retryable=True) from exc
    for name, content in (("stdout", proc.stdout), ("stderr", proc.stderr)):
        # Keep diagnostics outside machine stdout, with credential masking.
        clean = mask_secrets(content)
        (diagnostics_dir / (name + ".log")).write_text(clean, encoding="utf-8")
        if clean:
            print(clean[-4000:], file=sys.stderr, end="" if clean.endswith("\n") else "\n")
    if proc.returncode:
        raise PlanSaveError("mpp_unreadable")
    try:
        payload = json.loads(output.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PlanSaveError("invalid_reader_export") from exc
    return payload


def _quality(data, details_ref):
    warnings = []
    def add(code, message):
        warnings.append({"code": code, "message": message, "details_ref": details_ref})
    if data["resolved_timezone"] is None:
        add("timezone_unknown", "Исходные даты сохранены без подтверждённой таймзоны")
    for name, info in data["collections"].items():
        if info["status"] != "complete":
            add("collection_" + name + "_" + info["status"], "Полнота коллекции " + name + ": " + info["status"])
    qualities = set()
    def walk(value):
        if isinstance(value, dict):
            quality = value.get("quality")
            if isinstance(quality, str) and quality in ("missing", "unsupported", "partial"):
                qualities.add(quality)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    walk(data)
    for quality in sorted(qualities):
        add("fields_" + quality, "Часть исходных полей имеет качество " + quality)
    for name in ("tasks", "dependencies", "resources", "assignments", "calendars"):
        if any("error" in row for row in data[name]):
            add("unreadable_" + name, "Непрочитанные строки коллекции " + name + " явно сохранены")
    graph = data["diagnose_graph"]
    for key in ("multiple_roots", "has_cycle", "self_references", "dangling_dependencies", "dangling_endpoints",
                "external_dependencies", "external_records"):
        if graph.get(key):
            add("graph_" + key, "Проблема структуры сохранена в архиве: " + key)
    return warnings


def _failure(receipt, exc):
    if isinstance(exc, PlanSaveError):
        code, exit_code, retryable = exc.code, exc.exit_code, exc.retryable
    elif isinstance(exc, PlanBindingError):
        code = str(exc).split(":")[0]
        exit_code, retryable = (2 if code in ("project_slug_required", "invalid_project_slug_or_plan_key") else 4), False
    elif isinstance(exc, InputError):
        code, exit_code, retryable = exc.code, (4 if "conflict" in exc.code else 5), False
    elif isinstance(exc, (w.PlanWriterError, q.PlanQueryError)):
        code = str(exc).split(":")[0]
        exit_code, retryable = (4 if "conflict" in code or code == "source_hash_mismatch" else 5), False
    elif isinstance(exc, (ValueError, TypeError, KeyError, SchemaValidationError)):
        code, exit_code, retryable = "invalid_snapshot", 5, False
    else:
        code, exit_code, retryable = "archive_unavailable", 5, True
    receipt.update(status="conflict" if exit_code == 4 else "failed", exit_code=exit_code,
                   error={"code": code, "message": "Сохранение не подтверждено: " + code,
                          "retryable": retryable, "next_action": "Проверить архив и повторить операцию" if retryable else None})
    return receipt


def _readback_result(conn, operation, receipt, context):
    # This query is first on recovery, including before runtime selection/cache.
    committed = q.get_committed_import(conn, operation.item_id)
    if not committed:
        return None
    item, snapshot = committed["item"], committed["snapshot"]
    receipt["snapshot_id"] = item["snapshot_id"]  # Retain even on read-back failure.
    if not snapshot:
        raise w.PlanWriterError("snapshot_missing")
    reconcile_import(conn, operation.item_id)
    data = json.loads(snapshot["source_json"])
    validate_export({**data, "provenance": data["source_identity"]})
    export_artifact = q.find_artifact_by_hash(conn, snapshot["normalized_data_sha256"])
    if not export_artifact:
        raise w.PlanWriterError("normalized_export_missing")
    w.verify_artifact(conn, export_artifact["artifact_id"], snapshot["normalized_data_sha256"])
    if Path(export_artifact["path"]).read_bytes() != snapshot["source_json"].encode():
        raise w.PlanWriterError("normalized_export_mismatch")
    line = q.get_lineage(conn, snapshot["lineage_id"])
    project = q.resolve_plan(conn, receipt["project_slug"]) if receipt["project_slug"] else None
    if not project or project["plan_id"] != snapshot["plan_id"] or not line or line["plan_id"] != snapshot["plan_id"]:
        raise w.PlanWriterError("operation_binding_conflict")
    warnings = _quality(data, export_artifact["path"])
    receipt.update(status="unchanged" if item["status"] == "unchanged" else "saved_with_warnings" if warnings else "saved",
                   exit_code=0, error=None, warnings=warnings,
                   task_count=sum("error" not in t for t in data["tasks"]),
                   display_task_count=sum("error" not in t and t.get("id") != 0 for t in data["tasks"]),
                   dependency_count=sum("error" not in d for d in data["dependencies"]),
                   completed_stages=["input_frozen", "prepared", "archived"])
    receipt["verification"]["archive"] = "verified"
    receipt["verification"]["schedule"]["limitations"] = [warning["code"] for warning in warnings] + ["schedule_not_verified"]
    return {"plan_id": snapshot["plan_id"], "lineage_id": snapshot["lineage_id"],
            "mpp_artifact_id": snapshot["source_artifact_id"], "export_artifact_id": export_artifact["artifact_id"],
            "export_sha256": export_artifact["raw_sha256"]}


def save_frozen_input(artifact: FrozenInput, *, sha256: str, context: PlanContext,
                      operation: ImportOperation, export: dict | None = None) -> SaveResult:
    """Save *registered frozen* bytes; never accepts/reopens an original path.

    artifact/hash/context/operation are mandatory. Context and intake must match
    SQL exactly; future batch callers cannot accidentally trigger a second freeze.
    A committed link is read back before any runtime/reader/cache access.
    """
    receipt = single_receipt(operation_id=operation.operation_id, item_id=operation.item_id)
    counters = {"MPXJ_read": 0, "cache_hit": 0, "cache_miss": 0, "POST": 0, "PUT": 0}
    metadata = {}
    timings = {}
    started = time.monotonic()
    authorized = False
    conn = None
    try:
        conn = connect_durable(context.db)
        ensure_plan_schema(conn)
        row = q.get_operation(conn, operation.operation_id)
        item = q.get_import_item(conn, operation.item_id)
        attempt = q.get_attempt(conn, operation.attempt_id)
        if not row or row["action"] != "save" or not item or item["operation_id"] != operation.operation_id or not attempt or attempt["item_id"] != operation.item_id:
            raise PlanSaveError("operation_item_mismatch", exit_code=4)
        saved_context = json.loads(row["context_json"])
        if saved_context["fingerprint"] != context.snapshot()["fingerprint"]:
            raise PlanSaveError("operation_context_conflict", exit_code=4)
        request = saved_context["save"]
        receipt["project_slug"] = request.get("project_slug")
        if not receipt["project_slug"] and row["plan_id"]:
            binding = resolve_plan_binding(request.get("page_id"), conn=conn)
            receipt["project_slug"] = binding["project_slug"]
        receipt["source"] = {"name": item["original_name"], "sha256": item["source_mpp_sha256"], "size_bytes": item["size_bytes"]}
        if sha256 != artifact.sha256 or sha256 != item["source_mpp_sha256"] or str(artifact.mpp_path) != item["frozen_locator"] or artifact.size_bytes != item["size_bytes"]:
            raise PlanSaveError("frozen_input_conflict", exit_code=4)
        authorized = True
        # Recovery does not depend on original input, disposable cache or JVM.
        readback_started = time.monotonic()
        metadata = _readback_result(conn, operation, receipt, context) or {}
        timings["readback"] = time.monotonic() - readback_started
        if not metadata:
            if not artifact.mpp_path.is_file() or hashlib.sha256(artifact.mpp_path.read_bytes()).hexdigest() != sha256:
                raise PlanSaveError("frozen_input_corrupt")
            context.check_input_size(artifact.mpp_path.stat().st_size)
            receipt["completed_stages"].append("input_frozen")
            profile_path = PROFILES / (context.settings["NORMALIZATION_PROFILE"] + ".json")
            if hashlib.sha256(profile_path.read_bytes()).hexdigest() != saved_context["profiles"]["NORMALIZATION_PROFILE"]["sha256"]:
                raise PlanSaveError("normalization_profile_changed", exit_code=4)
            parse_started = time.monotonic()
            if export is None:
                try:
                    runtime = select_mpxj_python(settings=Settings(context.settings, context.sources))
                except RuntimeError as exc:
                    raise PlanSaveError("mpxj_runtime_unavailable", retryable=True) from exc
                material = ParseCache.material(sha256, reader=runtime.versions, export_version="full-export-v2")
                cache = ParseCache(context.cache_dir, counters=counters)
                try:
                    export = cache.get_or_parse(artifact.mpp_path, material,
                        parser=lambda source: run_export_full(source, context=context, runtime=runtime,
                            diagnostics_dir=context.workvault / "_plan-receipts" / operation.operation_id / operation.attempt_id))
                except Exception:
                    # The exporter telemetry is unavailable when its process fails;
                    # do not misreport an attempted read as measured zero.
                    counters["MPXJ_read"] = None
                    raise
            timings["parse_cache"] = time.monotonic() - parse_started
            normalize_started = time.monotonic()
            validate_export(export)
            if export["provenance"]["sha256"] != sha256 or export["provenance"]["size_bytes"] != artifact.size_bytes:
                raise PlanSaveError("source_hash_mismatch", exit_code=4)
            prepared = PreparedPlan.from_export(export, profile=NormalizationProfile.load(profile_path),
                timezone_hint=request.get("timezone_hint"), provenance={"original_name": artifact.original_name,
                "source_path": artifact.original_locator, "source_origin": "zip" if artifact.container_sha256 else "local_file"})
            # Durable even if binding is unresolved or commit fails later.
            prepared_path = write_receipt(operation.operation_id, "prepared", prepared.to_dict(), workvault=context.workvault)
            receipt["completed_stages"].append("prepared")
            receipt["warnings"] = _quality(prepared.normalized_data, str(prepared_path))
            timings["normalization_quality"] = time.monotonic() - normalize_started
            w.record_operation_event(conn, operation.attempt_id, "prepared", detail=json.dumps({"path": str(prepared_path),
                "semantic_sha256": prepared.semantic_hash, "counters": counters}, sort_keys=True))
            archive_started = time.monotonic()
            binding = resolve_plan_binding(request.get("page_id"), request.get("project_slug"),
                                            lineage_id=request.get("lineage_id"), conn=conn)
            receipt["project_slug"] = binding["project_slug"]
            source_id, digest = store_artifact(artifact.mpp_path, "mpp", project_slug=binding["project_slug"], conn=conn, workvault=context.workvault)
            if digest != sha256:
                raise PlanSaveError("source_hash_mismatch", exit_code=4)
            spec = build_snapshot_spec(prepared.to_dict(), plan_id=binding["plan_id"], lineage_id=binding["lineage_id"], source_artifact_id=source_id)
            # Keep SQL item status aligned with actual archive warnings. An ID=0
            # service row is normal source data; its informational diagnostic
            # alone must not turn a complete save into saved_with_warnings.
            issues = tuple(issue for issue in spec.quality_issues if issue.severity != "info")
            kinds = {issue.issue_kind for issue in issues}
            extra = tuple(w.QualityIssueSpec(warning["code"], "warning", warning["message"])
                          for warning in receipt["warnings"]
                          if warning["code"].removeprefix("graph_") not in kinds)
            spec = replace(spec, quality_issues=issues + extra)
            # Same canonical bytes/hash as the typed snapshot (not the pretty JSON envelope).
            store_artifact(spec.source_json.encode(), "export_json", project_slug=binding["project_slug"],
                           ext="json", conn=conn, workvault=context.workvault)
            committed = w.commit_import_snapshot(conn, operation.item_id, operation.attempt_id, spec)
            receipt["snapshot_id"] = committed.snapshot_id
            timings["archive_commit"] = time.monotonic() - archive_started
            readback_started = time.monotonic()
            metadata = _readback_result(conn, operation, receipt, context) or {}
            timings["readback"] += time.monotonic() - readback_started
    except Exception as exc:
        _failure(receipt, exc)
        if receipt["snapshot_id"]:
            receipt["verification"]["archive"] = "failed"
        if conn is not None and authorized:
            # Unknown commit outcome must be resolved by query, never reinserted.
            try:
                linked = q.get_committed_import(conn, operation.item_id)
                if linked:
                    receipt["snapshot_id"] = linked["item"]["snapshot_id"]
                else:
                    w.fail_import_item(conn, operation.item_id, operation.attempt_id, receipt["error"]["code"], retryable=receipt["error"]["retryable"])
            except (sqlite3.Error, w.PlanWriterError, q.PlanQueryError):
                pass
    finally:
        if conn is not None and authorized:
            try:
                w.record_operation_event(conn, operation.attempt_id, "save_metrics", detail=json.dumps({"counters": counters, "duration_seconds": time.monotonic()-started, "stage_durations_seconds": timings}))
                receipt = finish_archive_operation(conn, operation, receipt, context=context)
            except Exception:
                receipt = _failure(receipt, PlanSaveError("sql_result_unavailable", retryable=True))
        if conn is not None:
            conn.close()
    return SaveResult(mask_secrets(receipt), counters=counters, **metadata)


def save_snapshot(mpp_path: str | Path, *, page_id=None, project_slug=None, lineage_id=None,
                  timezone_hint=None, source_version_date=None, context: PlanContext | None = None,
                  db_path=None, workvault=None, cache_dir=None, export=None) -> SaveResult:
    """Register one arrival and freeze once, then use the common frozen contract."""
    receipt = single_receipt(project_slug=project_slug)
    operation = None
    conn = None
    try:
        validate_save_arguments(timezone_hint=timezone_hint, source_version_date=source_version_date)
        context = context or PlanContext.resolve(db=db_path, workvault=workvault, cache_dir=cache_dir)
        conn = connect_durable(context.db)
        ensure_plan_schema(conn)
        request = {"page_id": page_id, "project_slug": project_slug, "lineage_id": lineage_id, "timezone_hint": timezone_hint,
                   "source_version_date": source_version_date}
        operation = begin_import(conn, mpp_path, context={**context.snapshot(), "save": request},
            source_version_date=source_version_date, source_version_basis="explicit_user" if source_version_date else None)
        receipt.update(operation_id=operation.operation_id, item_id=operation.item_id)
        freeze_started = time.monotonic()
        frozen = freeze_operation_input(conn, operation)
        w.record_operation_event(conn, operation.attempt_id, "input_metrics", detail=json.dumps({"duration_seconds": time.monotonic()-freeze_started}))
    except Exception as exc:
        _failure(receipt, exc)
        if conn is not None and operation:
            try:
                if isinstance(exc, InputError) and exc.candidates:
                    diagnostic = write_receipt(operation.operation_id, "input-error", {"code": exc.code,
                        "candidates": list(exc.candidates)}, workvault=context.workvault)
                    receipt["error"]["next_action"] = "Выбрать один MPP; список кандидатов: " + str(diagnostic)
                w.fail_import_item(conn, operation.item_id, operation.attempt_id, receipt["error"]["code"], retryable=receipt["error"]["retryable"])
                receipt = finish_archive_operation(conn, operation, receipt, context=context)
            except Exception:
                _failure(receipt, PlanSaveError("sql_result_unavailable", retryable=True))
        return SaveResult(mask_secrets(receipt))
    finally:
        if conn is not None:
            conn.close()
    return save_frozen_input(frozen, sha256=frozen.sha256, context=context, operation=operation, export=export)
