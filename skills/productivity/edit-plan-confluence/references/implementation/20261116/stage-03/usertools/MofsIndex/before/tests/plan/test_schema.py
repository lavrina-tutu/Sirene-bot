"""Тесты безопасности plan_*-схемы относительно rebuild индекса встреч/docs.

P0.SAFE.3/4 (R-020, AC-121): drop_all()/drop_docs() не должны знать о plan_*-
таблицах; явный rebuild через публичный API индексатора не должен их
затрагивать.
"""
from __future__ import annotations

import pytest

from mofs_index.db import connect, initialize, drop_all, drop_docs
from mofs_index.plan.migrate import ensure_plan_schema
from mofs_index.plan.schema import all_plan_table_names


@pytest.fixture
def conn_with_plan(tmp_path):
    db_path = tmp_path / "index.sqlite"
    conn = connect(db_path, durable=True)
    initialize(conn)
    ensure_plan_schema(conn)
    yield conn
    conn.close()


def test_drop_all_preserves_plan_tables(conn_with_plan):
    conn = conn_with_plan
    # Зафиксировать строку в plan_schema_migration (единственная plan_*-таблица
    # Фазы 0) и убедиться, что drop_all()+initialize() её не трогает.
    before = conn.execute("SELECT COUNT(*) FROM plan_schema_migration").fetchone()[0]
    assert before >= 1  # phase0-baseline уже применена ensure_plan_schema

    drop_all(conn)
    initialize(conn)

    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    for plan_table in all_plan_table_names():
        assert plan_table in tables, f"{plan_table} не должна исчезать после drop_all()"

    after = conn.execute("SELECT COUNT(*) FROM plan_schema_migration").fetchone()[0]
    assert after == before, "drop_all() не должен был очищать plan_schema_migration"


def test_drop_docs_preserves_plan_tables(conn_with_plan):
    conn = conn_with_plan
    drop_docs(conn)
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    for plan_table in all_plan_table_names():
        assert plan_table in tables


def test_drop_all_table_list_has_no_plan_wildcard():
    """Статическая проверка: drop_all() явно перечисляет только 4 существующие
    таблицы встреч/docs и не содержит plan_*-имён (защита от будущей правки)."""
    import inspect
    from mofs_index import db as db_module

    src = inspect.getsource(db_module.drop_all)
    assert "plan_" not in src, "drop_all() не должен упоминать plan_*-таблицы"


def test_ensure_plan_schema_idempotent(conn_with_plan):
    conn = conn_with_plan
    applied_again = ensure_plan_schema(conn)
    assert applied_again == [], "повторный вызов не должен переприменять миграции"
