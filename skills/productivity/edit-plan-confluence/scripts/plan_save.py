"""Явная команда ``save`` (P4.ACC.2, R-008, AC-144): сохранить снимок MPP,
НЕ публиковать, НЕ сдвигать baseline.

Поток: архив байтов MPP (content-addressed, ``plan_archive.store_artifact``)
→ полный нормализованный экспорт MPP (``MppReader/plan_export.export_full``,
вызывается subprocess-ом в интерпретаторе с mpxj/jpype — та же логика выбора
интерпретатора, что и ``mpp_input.py::_pick_python``) → архив JSON экспорта
→ ``mofs_index.plan.writer.ingest_snapshot`` (одна транзакция, P2.SCHEMA.5).

Эта функция НАМЕРЕННО не вызывает:
- ``plan_writer.record_publication`` / ``plan_writer.link_publication_page``
  (таблица ``plan_publication`` не меняется — ни одна новая публикация не
  появляется, AC-144);
- ``plan_writer.select_snapshot_baseline`` / ``select_plan_baseline``
  (``plan_baseline_selection``/``plan_snapshot_selection`` не трогаются —
  default baseline не сдвигается, R-008/AC-144);
- никаких сетевых вызовов Confluence (``save`` работает только с локальным
  MPP-файлом; ``page_id`` используется только чтобы привязаться к уже
  существующей ``plan_lineage`` той же страницы, без GET/POST/PUT).
"""
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mpp_input import _pick_python
from plan_archive import get_plan_db_path, resolve_plan_binding, store_artifact
from plan_receipt import write_receipt

MOFS_INDEX_ROOT = Path.home() / "USERTOOLS" / "MofsIndex"
if str(MOFS_INDEX_ROOT) not in sys.path:
    sys.path.insert(0, str(MOFS_INDEX_ROOT))

from mofs_index.db import connect_durable  # noqa: E402
from mofs_index.plan import ingest_mpp  # noqa: E402
from mofs_index.plan import writer as plan_writer  # noqa: E402

MPPREADER_ROOT = Path.home() / "USERTOOLS" / "MppReader"
PLAN_EXPORT_SCRIPT = MPPREADER_ROOT / "plan_export.py"

LOCAL_SAVE_NAMESPACE = "local-save"


class PlanSaveError(RuntimeError):
    """save-only операция не может быть завершена (см. сообщение)."""


@dataclass
class SaveResult:
    snapshot_id: str
    plan_id: str
    lineage_id: str
    project_slug: str
    mpp_artifact_id: str
    mpp_sha256: str
    export_artifact_id: str
    export_sha256: str
    task_count: int
    dependency_count: int
    published: bool = False  # инвариант: всегда False для save-only


def run_export_full(mpp_path: Path, *, timeout: int = 180) -> dict[str, Any]:
    """Запустить ``plan_export.export_full`` subprocess-ом в JVM-окружении."""
    python = _pick_python()
    proc = subprocess.run(
        [python, str(PLAN_EXPORT_SCRIPT), str(mpp_path)],
        capture_output=True, text=True, timeout=timeout,
    )
    if proc.returncode != 0:
        raise PlanSaveError(
            f"plan_export.export_full завершился с ошибкой (python={python}): "
            f"{(proc.stderr or proc.stdout)[-1500:]}"
        )
    stdout = proc.stdout
    # JVM/log4j иногда пишет диагностическую строку в stdout перед JSON
    # (наблюдаемый факт окружения: "Log4j API could not find a logging
    # provider" — не ошибка plan_export, не трогаем MppReader ради этого).
    # Отрезаем всё до первой '{', не меняя сам экспорт.
    brace = stdout.find("{")
    if brace > 0:
        stdout = stdout[brace:]
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise PlanSaveError(
            f"plan_export.export_full вернул непарсимый JSON (python={python}): {exc}; "
            f"raw_tail={proc.stdout[-500:]!r}"
        ) from exc


def save_snapshot(
    mpp_path: str | Path,
    *,
    page_id: str | None = None,
    project_slug: str | None = None,
    timezone_hint: str | None = None,
    db_path: Path | None = None,
    export: dict[str, Any] | None = None,
) -> SaveResult:
    """Сохранить snapshot MPP БЕЗ публикации и БЕЗ сдвига baseline (AC-144).

    ``page_id`` — опционален. Если задан, привязка идёт через уже
    существующую (или новую, если ``project_slug`` передан явно) Confluence
    ``plan_lineage`` той же страницы — но эта функция не делает ни одного
    сетевого вызова к Confluence. Без ``page_id`` требуется явный
    ``project_slug`` — заводится служебная lineage в пространстве имён
    ``local-save`` (не пересекается с Confluence lineage той же страницы).

    ``export`` — для тестов: заранее посчитанный словарь
    ``plan_export.export_full()``, чтобы не требовать JVM/mpxj в unit-тестах.
    """
    mpp_path = Path(mpp_path).resolve()
    if not mpp_path.is_file():
        raise FileNotFoundError(f"MPP input not found: {mpp_path}")

    if export is None:
        export = run_export_full(mpp_path)

    conn = connect_durable(db_path or get_plan_db_path())
    try:
        if page_id:
            binding = resolve_plan_binding(page_id, project_slug, conn=conn)
        else:
            if not project_slug:
                raise PlanSaveError(
                    "project_slug обязателен без page_id (аналог R-007 §4.2: "
                    "привязка не угадывается)"
                )
            binding = resolve_plan_binding(None, project_slug, conn=conn)

        mpp_artifact_id, mpp_sha256 = store_artifact(
            mpp_path, "mpp", project_slug=binding["project_slug"], conn=conn,
        )
        export_bytes = json.dumps(export, ensure_ascii=False, default=str).encode("utf-8")
        export_artifact_id, export_sha256 = store_artifact(
            export_bytes, "export_json", project_slug=binding["project_slug"],
            ext="json", conn=conn,
        )

        spec = ingest_mpp.build_snapshot_spec(
            export,
            plan_id=binding["plan_id"],
            lineage_id=binding["lineage_id"],
            source_artifact_id=mpp_artifact_id,
            representation="mpp",
            timezone_hint=timezone_hint,
            published_at=None,
            observed_at=None,
        )
        # P4.ACC.2 инвариант (AC-144): ingest_snapshot пишет ТОЛЬКО snapshot-
        # таблицы (plan_snapshot + дочерние). Ни одна строка plan_publication/
        # plan_publication_snapshot/plan_snapshot_selection/
        # plan_baseline_selection здесь не создаётся и не меняется.
        snapshot_id = plan_writer.ingest_snapshot(conn, spec)
    finally:
        conn.close()

    write_receipt(f"save-{snapshot_id}", "save", {
        "stage": "save", "status": "snapshot_created_not_published",
        "snapshot_id": snapshot_id,
        "plan_id": binding["plan_id"],
        "lineage_id": binding["lineage_id"],
        "mpp_artifact_id": mpp_artifact_id, "mpp_sha256": mpp_sha256,
        "export_artifact_id": export_artifact_id, "export_sha256": export_sha256,
        "task_count": len(spec.tasks), "dependency_count": len(spec.dependencies),
    })

    return SaveResult(
        snapshot_id=snapshot_id,
        plan_id=binding["plan_id"],
        lineage_id=binding["lineage_id"],
        project_slug=binding["project_slug"],
        mpp_artifact_id=mpp_artifact_id,
        mpp_sha256=mpp_sha256,
        export_artifact_id=export_artifact_id,
        export_sha256=export_sha256,
        task_count=len(spec.tasks),
        dependency_count=len(spec.dependencies),
    )
