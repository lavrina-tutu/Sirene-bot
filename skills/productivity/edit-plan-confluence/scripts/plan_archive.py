"""Разрешение plan/lineage и content-addressed архив байтов (P1.W1.1/1.2).

Обёртка над ``mofs_index.plan.writer`` — ни одна функция этого модуля не
пишет свободный SQL; вся запись идёт через typed writer API Фазы 1.

Таймзона ZD (Q3, R-013) — явная константа здесь, не в MppReader/``plan_export``
(план §2.2, таблица файлов): по умолчанию анализ не угадывает основание
хранения дат, для ZD оно зафиксировано владельцем.
"""
from __future__ import annotations

import hashlib
import os
import re
import tempfile
import sqlite3
import sys
from pathlib import Path

from env import get_workvault_path

MOFS_INDEX_ROOT = Path.home() / "USERTOOLS" / "MofsIndex"
if str(MOFS_INDEX_ROOT) not in sys.path:
    sys.path.insert(0, str(MOFS_INDEX_ROOT))

from mofs_index.db import DEFAULT_DB_PATH, connect_durable  # noqa: E402
from mofs_index.plan import query as plan_query
from mofs_index.plan import writer as plan_writer  # noqa: E402

CONFLUENCE_NAMESPACE = "confluence:dom.tutu.ru"
# Решено Сашей (Q3, DECISIONS-owner.md, 13.11.2026): таймзона исходных
# локальных дат плана ZD. Константа здесь, НЕ в plan_export.py (R-013 §6).
ZD_TIMEZONE_HINT = "Europe/Moscow"
ZD_TIMEZONE_BASIS = "owner_decision_Q3_20261113"


class PlanBindingError(RuntimeError):
    """Привязка plan/lineage к странице не может быть разрешена автоматически."""


def get_plan_db_path() -> Path:
    return DEFAULT_DB_PATH


def _connect(db_path: Path | None = None) -> sqlite3.Connection:
    return connect_durable(db_path or get_plan_db_path())


def _safe_component(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*",value) or ".." in value:
        raise PlanBindingError("invalid_project_slug_or_plan_key")
    return value


def resolve_plan_binding(page_id: str | None, project_slug: str | None = None, *,
                         lineage_id: str | None = None, db_path: Path | None = None,
                         conn: sqlite3.Connection | None = None) -> dict[str,str]:
    if project_slug is not None:
        _safe_component(project_slug)
    own_conn=conn is None
    c=conn or _connect(db_path)
    try:
        from mofs_index.plan.migrate import ensure_plan_schema
        ensure_plan_schema(c)
        bindings=plan_query.page_bindings(c,page_id,CONFLUENCE_NAMESPACE) if page_id else []
        if len(bindings)>1:
            raise PlanBindingError("binding_conflict: contradictory page bindings")
        if bindings:
            binding=bindings[0]
            if project_slug is not None and binding["project_slug"] != project_slug:
                raise PlanBindingError("binding_conflict: explicit project differs from page binding")
            if lineage_id and binding["lineage_id"] != lineage_id:
                raise PlanBindingError("binding_conflict: explicit lineage differs from page binding")
            return binding
        if not project_slug:
            raise PlanBindingError("project_slug_required")
        plan_id=plan_writer.ensure_plan(c,project_slug,name=project_slug,
            md_path=f"Entities/{project_slug}/Pages/{project_slug}.ganttchart.md")
        if lineage_id:
            row=plan_query.get_lineage(c,lineage_id)
            if not row or row["plan_id"] != plan_id:
                raise PlanBindingError("binding_conflict: lineage belongs to another project")
            if page_id and (row["page_id"] != page_id or row["source_namespace"] != CONFLUENCE_NAMESPACE):
                raise PlanBindingError("binding_conflict: lineage page differs")
        else:
            # A fresh stable local archive line; legacy filename-based lines remain intact.
            lineage_id=plan_writer.ensure_lineage(c,plan_id,CONFLUENCE_NAMESPACE if page_id else "local-archive-v1",
                                                page_id=page_id,basis="explicit" if page_id else "project_archive_v1")
        return {"plan_id":plan_id,"lineage_id":lineage_id,"project_slug":project_slug}
    finally:
        if own_conn:
            c.close()


def _ext_for_kind(kind: str, hint: str | None = None) -> str:
    if hint:
        return hint.lstrip(".")
    return {
        "mpp": "mpp",
        "prepared_json": "json",
        "downloaded_json": "json",
        "storage_snapshot": "html",
    }.get(kind, "bin")


def store_artifact(
    path_or_bytes: Path | bytes,
    kind: str,
    *,
    project_slug: str,
    plan_key: str | None = None,
    ext: str | None = None,
    db_path: Path | None = None,
    conn: sqlite3.Connection | None = None,
    workvault: Path | None = None,
) -> tuple[str, str]:
    """Сохранить артефакт content-addressed путём и зарегистрировать его в SQL.

    Возвращает ``(artifact_id, sha256)``. Дедупликация по hash — повторный
    вызов с теми же байтами не создаёт вторую копию файла/строку (AC-103).
    """
    if isinstance(path_or_bytes, (str, Path)):
        data = Path(path_or_bytes).read_bytes()
    else:
        data = path_or_bytes
    sha256 = hashlib.sha256(data).hexdigest()

    project_slug=_safe_component(project_slug)
    plan_key=_safe_component(plan_key or f"{project_slug}.ganttchart")
    archive_dir=(Path(workvault) if workvault is not None else get_workvault_path())/"Entities"/project_slug/"Sources"/"plans"/plan_key/"artifacts"
    extension=_safe_component(_ext_for_kind(kind,ext))
    own_conn=conn is None
    c=conn or _connect(db_path)
    try:
        from mofs_index.plan.migrate import ensure_plan_schema
        ensure_plan_schema(c)
        existing=plan_query.find_artifact_by_hash(c,sha256)
        if existing:
            plan_writer.verify_artifact(c,existing["artifact_id"],sha256)
            return existing["artifact_id"],sha256
        archive_dir.mkdir(parents=True,exist_ok=True)
        dest=archive_dir/f"{sha256}.{extension}"
        if dest.exists():
            if hashlib.sha256(dest.read_bytes()).hexdigest() != sha256:
                raise plan_writer.PlanWriterError("artifact_hash_mismatch")
        else:
            fd,name=tempfile.mkstemp(prefix=".artifact-",dir=archive_dir)
            temp=Path(name)
            try:
                with os.fdopen(fd,"wb") as target:
                    target.write(data)
                    target.flush()
                    os.fsync(target.fileno())
                # Hard-link installs without overwriting any concurrent winner.
                try:
                    os.link(temp,dest)
                except FileExistsError:
                    if hashlib.sha256(dest.read_bytes()).hexdigest() != sha256:
                        raise plan_writer.PlanWriterError("artifact_hash_mismatch")
                from mpp_input import _sync_dir
                _sync_dir(archive_dir)
            finally:
                temp.unlink(missing_ok=True)
        artifact_id=plan_writer.record_artifact(c,sha256,kind,str(dest),format=extension,size_bytes=len(data))
        plan_writer.verify_artifact(c,artifact_id,sha256)
        return artifact_id,sha256
    finally:
        if own_conn:
            c.close()
