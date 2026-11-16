"""Internal durable operation/attempt adapter. No CLI, SQL or separate journal."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from plan_archive import store_artifact
from mofs_index.plan import writer as w, query as q
from mofs_index.plan.ingest_mpp import build_snapshot_spec
from mpp_input import FrozenInput, InputError, freeze_input
from plan_reconcile import reconcile_import


@dataclass(frozen=True)
class ImportOperation:
    operation_id: str
    item_id: str
    attempt_id: str


def begin_import(conn, path: str | Path, *, context, action="save", operation_id=None,
                 item_id=None, batch_id=None, ordinal=0, source_version_date=None, source_version_basis=None):
    """Register before project resolution. Repeats reuse operation/item, add attempt."""
    snapshot=context.snapshot() if hasattr(context,"snapshot") else context
    document=json.dumps(snapshot,ensure_ascii=False,sort_keys=True,separators=(",", ":"))
    existing=q.get_operation(conn,operation_id) if operation_id else None
    if existing:
        if existing["action"] != action:
            raise w.PlanWriterError("operation_context_conflict")
        # Resume uses the persisted effective context, never changed defaults.
        document=existing["context_json"]
    operation_id=w.create_operation(conn,w.OperationSpec(action,document,operation_id))
    item=w.create_import_item(conn,w.ImportItemSpec(operation_id,Path(path).name,str(Path(path).absolute()),
        item_id=item_id,batch_id=batch_id,ordinal=ordinal,source_version_date=source_version_date,
        source_version_basis=source_version_basis))
    attempt=w.begin_operation_attempt(conn,operation_id,item)
    return ImportOperation(operation_id,item,attempt)


def freeze_operation_input(conn, operation: ImportOperation) -> FrozenInput:
    item=q.get_import_item(conn,operation.item_id)
    if not item or item["operation_id"] != operation.operation_id:
        raise w.PlanWriterError("operation_item_mismatch")
    if item["frozen_locator"]:
        source=Path(item["frozen_locator"])
        if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != item["source_mpp_sha256"]:
            raise InputError("frozen_input_corrupt")
        if item["container_sha256"]:
            container=Path(item["container_locator"])
            if not container.is_file() or hashlib.sha256(container.read_bytes()).hexdigest() != item["container_sha256"]:
                raise InputError("frozen_container_corrupt")
        return FrozenInput(source,item["source_mpp_sha256"],item["size_bytes"],item["original_name"],item["original_locator"],
            item["frozen_at"],item["container_sha256"],item["container_locator"],item["zip_member"])
    context=json.loads(q.get_operation(conn,operation.operation_id)["context_json"])
    try:
        frozen=freeze_input(item["original_locator"],operation_id=operation.operation_id,
                            workvault=Path(context["paths"]["workvault"]),settings=context["settings"])
        w.freeze_import_item(conn,operation.item_id,frozen_locator=str(frozen.mpp_path),source_mpp_sha256=frozen.sha256,
            size_bytes=frozen.size_bytes,frozen_at=frozen.frozen_at,container_sha256=frozen.container_sha256,
            container_locator=frozen.container_locator,zip_member=frozen.zip_member)
        w.record_operation_event(conn,operation.attempt_id,"input_frozen",detail=operation.item_id)
        return frozen
    except InputError as exc:
        w.fail_import_item(conn,operation.item_id,operation.attempt_id,exc.code,
                           container_sha256=getattr(exc,"container_sha256",None),container_locator=getattr(exc,"container_locator",None))
        raise


def commit_prepared_import(conn, operation: ImportOperation, *, binding: dict, prepared: dict, receipt_writer=None):
    # Recovery is always first; a committed input never invokes parser or freeze.
    recovered=reconcile_import(conn,operation.item_id,receipt_writer=receipt_writer)
    if recovered:
        return recovered
    from prepared_plan import PreparedPlan
    PreparedPlan(prepared).validate()
    item=q.get_import_item(conn,operation.item_id)
    if not item or not item["frozen_locator"]:
        raise w.PlanWriterError("input_not_frozen")
    context=json.loads(q.get_operation(conn,operation.operation_id)["context_json"])
    artifact_id,digest=store_artifact(Path(item["frozen_locator"]),"mpp",project_slug=binding["project_slug"],
                                    conn=conn,workvault=Path(context["paths"]["workvault"]))
    if digest != item["source_mpp_sha256"]:
        raise w.PlanWriterError("source_hash_mismatch")
    spec=build_snapshot_spec(prepared,plan_id=binding["plan_id"],lineage_id=binding["lineage_id"],source_artifact_id=artifact_id)
    w.commit_import_snapshot(conn,operation.item_id,operation.attempt_id,spec)
    return reconcile_import(conn,operation.item_id,receipt_writer=receipt_writer)
