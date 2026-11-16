"""Миграционный раннер для plan_*-схемы (P0.SAFE.3/4).

``ensure_plan_schema(conn)`` — единственная точка входа, которая:
  1. создаёт реестр ``plan_schema_migration`` (идемпотентно, CREATE TABLE IF NOT EXISTS);
  2. применяет недостающие миграции из ``schema.MIGRATIONS`` по порядку,
     пропуская уже применённые по ``migration_id``;
  3. каждая миграция — одна транзакция (DDL + запись в реестр).

Explicit-вызов (CLI ``mofs-index plan-migrate`` либо прямой импорт из
``writer.py``/тестов) — НЕ вызывается автоматически из ``mofs_index.indexer``
или другого пути `mofs-index index`, чтобы не создавать побочный эффект в
несвязанном коде (план §4.2 п.3).
"""
from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone

from .schema import MIGRATIONS, PLAN_SCHEMA_MIGRATION_DDL, Migration


def _checksum(migration: Migration) -> str:
    h = hashlib.sha256()
    h.update(migration.migration_id.encode("utf-8"))
    for stmt in migration.statements:
        h.update(stmt.encode("utf-8"))
    return h.hexdigest()


def _applied_ids(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT migration_id FROM plan_schema_migration").fetchall()
    return {row[0] for row in rows}


def ensure_plan_schema(conn: sqlite3.Connection) -> list[str]:
    """Применить все недостающие миграции plan_*. Возвращает список применённых id.

    Идемпотентна: повторный вызов без новых миграций в коде ничего не делает.
    """
    conn.execute(PLAN_SCHEMA_MIGRATION_DDL)
    conn.commit()

    applied = _applied_ids(conn)
    newly_applied: list[str] = []
    for migration in MIGRATIONS:
        if migration.migration_id in applied:
            stored = conn.execute(
                "SELECT checksum FROM plan_schema_migration WHERE migration_id=?",
                (migration.migration_id,),
            ).fetchone()[0]
            if stored != _checksum(migration):
                raise ValueError(f"applied migration checksum mismatch: {migration.migration_id}")
            continue
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        checksum = _checksum(migration)
        try:
            conn.execute("BEGIN")
            for stmt in migration.statements:
                conn.execute(stmt)
            conn.execute(
                "INSERT INTO plan_schema_migration(migration_id, applied_at, checksum) "
                "VALUES (?, ?, ?)",
                (migration.migration_id, now, checksum),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        newly_applied.append(migration.migration_id)
    return newly_applied


def applied_migrations(conn: sqlite3.Connection) -> list[tuple[str, str, str]]:
    """Список (migration_id, applied_at, checksum) для диагностики/CLI."""
    conn.execute(PLAN_SCHEMA_MIGRATION_DDL)
    rows = conn.execute(
        "SELECT migration_id, applied_at, checksum FROM plan_schema_migration "
        "ORDER BY applied_at"
    ).fetchall()
    return [tuple(r) for r in rows]
