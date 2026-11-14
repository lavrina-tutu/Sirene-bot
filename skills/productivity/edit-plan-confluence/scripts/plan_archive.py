"""Разрешение plan/lineage и content-addressed архив байтов (P1.W1.1/1.2).

Обёртка над ``mofs_index.plan.writer`` — ни одна функция этого модуля не
пишет свободный SQL; вся запись идёт через typed writer API Фазы 1.

Таймзона ZD (Q3, R-013) — явная константа здесь, не в MppReader/``plan_export``
(план §2.2, таблица файлов): по умолчанию анализ не угадывает основание
хранения дат, для ZD оно зафиксировано владельцем.
"""
from __future__ import annotations

import hashlib
import shutil
import sqlite3
import sys
from pathlib import Path

from env import get_workvault_path

MOFS_INDEX_ROOT = Path.home() / "USERTOOLS" / "MofsIndex"
if str(MOFS_INDEX_ROOT) not in sys.path:
    sys.path.insert(0, str(MOFS_INDEX_ROOT))

from mofs_index.db import DEFAULT_DB_PATH, connect_durable  # noqa: E402
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


def resolve_plan_binding(
    page_id: str,
    project_slug: str | None = None,
    *,
    db_path: Path | None = None,
    conn: sqlite3.Connection | None = None,
) -> dict[str, str]:
    """Разрешить ``plan_id``/``lineage_id`` по ``pageId``.

    При первом вызове для нового ``pageId`` создаёт ``plan``+``plan_lineage``
    **только если** ``project_slug`` передан явно (R-007 §4.2: привязка не
    угадывается по internal title MPP). Повторный вызов с тем же ``page_id``
    возвращает уже созданную привязку независимо от переданного
    ``project_slug`` (идемпотентность по UQ).
    """
    own_conn = conn is None
    c = conn or _connect(db_path)
    try:
        row = c.execute(
            "SELECT lineage_id, plan_id FROM plan_lineage WHERE page_id = ? "
            "AND source_namespace = ?",
            (page_id, CONFLUENCE_NAMESPACE),
        ).fetchone()
        if row:
            lineage_id, plan_id = row
            slug_row = c.execute(
                "SELECT project_slug FROM plan WHERE plan_id = ?", (plan_id,)
            ).fetchone()
            return {
                "plan_id": plan_id,
                "lineage_id": lineage_id,
                "project_slug": slug_row[0] if slug_row else None,
            }
        if not project_slug:
            raise PlanBindingError(
                f"Нет привязки plan/lineage для pageId={page_id}; "
                "project_slug должен быть указан явно до первого архивного "
                "commit (R-007 §4.2: не угадывается по заголовку MPP)."
            )
        plan_id = plan_writer.ensure_plan(
            c,
            project_slug,
            name=project_slug,
            md_path=f"Entities/{project_slug}/Pages/{project_slug}.ganttchart.md",
        )
        lineage_id = plan_writer.ensure_lineage(
            c, plan_id, CONFLUENCE_NAMESPACE, page_id=page_id, basis="explicit",
        )
        return {"plan_id": plan_id, "lineage_id": lineage_id, "project_slug": project_slug}
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

    plan_key = plan_key or f"{project_slug}.ganttchart"
    archive_dir = get_workvault_path() / "Entities" / project_slug / "Sources" / "plans" / plan_key / "artifacts"
    archive_dir.mkdir(parents=True, exist_ok=True)
    extension = _ext_for_kind(kind, ext)
    dest = archive_dir / f"{sha256}.{extension}"
    if not dest.exists():
        if isinstance(path_or_bytes, (str, Path)):
            shutil.copy2(path_or_bytes, dest)
        else:
            dest.write_bytes(data)

    own_conn = conn is None
    c = conn or _connect(db_path)
    try:
        artifact_id = plan_writer.record_artifact(
            c, sha256, kind, str(dest), format=extension, size_bytes=len(data),
        )
    finally:
        if own_conn:
            c.close()
    return artifact_id, sha256
