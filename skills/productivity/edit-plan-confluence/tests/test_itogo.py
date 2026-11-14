from __future__ import annotations

import sys
from pathlib import Path

import pytest

from itogo import (
    apply_itogo,
    build_itogo_html,
    compute_itogo_from_csv,
    format_thousands,
    parse_itogo_text,
    patch_itogo,
    record_itogo_observation,
    strip_trudozatraty,
)
from macro import build_macro_html, macro_span

MOFS_ROOT = Path.home() / "USERTOOLS" / "MofsIndex"
if str(MOFS_ROOT) not in sys.path:
    sys.path.insert(0, str(MOFS_ROOT))


def test_itogo_from_csv_080926(tasks_csv, assignments_csv):
    d1, d2, n, m = compute_itogo_from_csv(tasks_csv, assignments_csv)
    assert d1 == "28.09.26"
    assert d2 == "18.05.27"
    assert n == 154
    assert m == 2356


def test_format_thousands():
    assert format_thousands(1960) == "1 960"
    assert format_thousands(2356) == "2 356"


def test_build_itogo_html():
    html = build_itogo_html("28.09.26", "18.05.27", 154, 2356)
    assert "Итого: с 28.09.26 по 18.05.27 - 154 рабочих дней" in html
    assert "Трудозатраты" not in html
    assert "70%" not in html


def test_patch_existing_itogo():
    storage = (
        "<p><strong>Итого: с 01.01.26 по 02.02.26 - 10 рабочих дней</strong></p>"
        "<p><strong>Трудозатраты: 100 человек-часа</strong></p>"
        "<p><strong>Загрузка 70% — не трогать</strong></p>"
        "<p>macro</p>"
    )
    out = patch_itogo(storage, "28.09.26", "18.05.27", 154, 2356)
    assert "28.09.26" in out
    assert "154" in out
    assert "Трудозатраты" not in out
    assert "человек-часа" not in out
    assert "2 356" not in out
    assert "Загрузка 70%" in out


def test_patch_existing_itogo_line1_only():
    storage = (
        "<p><strong>Итого: с 01.01.26 по 02.02.26 - 10 рабочих дней</strong></p>"
        "<p>macro</p>"
    )
    out = patch_itogo(storage, "28.09.26", "18.05.27", 154, 2356)
    assert out.count("Итого:") == 1
    assert "18.05.27" in out
    assert "154" in out
    assert "Трудозатраты" not in out


def test_insert_itogo_above_macro_no_block():
    macro_html = build_macro_html("new-macro-id", "pid", "phash")
    storage = "<p>Intro text</p>" + macro_html
    span = macro_span(storage)
    assert span is not None
    out = apply_itogo(storage, "28.09.26", "18.05.27", 154, 2356, macro_start=span[0])
    macro_pos = out.index("gantt-chart-planner")
    itogo_pos = out.index("Итого:")
    assert itogo_pos < macro_pos
    assert out.count("Итого:") == 1
    assert "154" in out
    assert "Трудозатраты" not in out


def test_apply_itogo_strips_line2_updates_line1():
    storage = (
        "<p><strong>Итого: с 01.01.26 по 02.02.26 - 10 рабочих дней</strong></p>"
        "<p><strong>Трудозатраты: 100 человек-часа</strong></p>"
        "<p><strong>Загрузка 70% — не трогать</strong></p>"
        "<p>macro</p>"
    )
    out = apply_itogo(storage, "28.09.26", "18.05.27", 154, 2356)
    assert "28.09.26" in out
    assert "18.05.27" in out
    assert "154" in out
    assert "Трудозатраты" not in out
    assert "Загрузка 70%" in out
    assert out.count("Итого:") == 1


def test_apply_itogo_line2_only_inserts_line1():
    macro_html = build_macro_html("new-macro-id", "pid", "phash")
    storage = "<p><strong>Трудозатраты: 100 человек-часа</strong></p>" + macro_html
    span = macro_span(storage)
    assert span is not None
    out = apply_itogo(storage, "28.09.26", "18.05.27", 154, 2356, macro_start=span[0])
    macro_pos = out.index("gantt-chart-planner")
    itogo_pos = out.index("Итого:")
    assert itogo_pos < macro_pos
    assert out.count("Итого:") == 1
    assert "Трудозатраты" not in out


def test_strip_trudozatraty_variants():
    canon = "<p><strong>Трудозатраты: 100 человек-часа</strong></p>"
    assert strip_trudozatraty(canon) == ""
    alt = "<p><strong>Трудозатраты: 50 человеко-часов</strong></p>"
    assert strip_trudozatraty(alt) == ""
    nbsp = "<p><strong>Трудозатраты: 2\xa0356 человек-часа</strong></p>"
    assert strip_trudozatraty(nbsp) == ""
    plain = "<p>Трудозатраты: 10 человек-часов</p>"
    assert "Трудозатраты" not in strip_trudozatraty(plain)
    assert strip_trudozatraty(strip_trudozatraty(canon)) == ""


def test_parse_itogo_text_found():
    storage = "<p><strong>Итого: с 01.01.26 по 02.02.26 - 10 рабочих дней</strong></p>"
    d1, d2, n = parse_itogo_text(storage)
    assert (d1, d2, n) == ("01.01.26", "02.02.26", 10)


def test_parse_itogo_text_missing_is_none_not_fabricated():
    d1, d2, n = parse_itogo_text("<p>нет итого тут</p>")
    assert (d1, d2, n) == (None, None, None)


@pytest.fixture
def plan_conn(tmp_path):
    from mofs_index.db import connect, initialize
    from mofs_index.plan.migrate import ensure_plan_schema
    from mofs_index.plan import writer as plan_writer

    c = connect(tmp_path / "index.sqlite", durable=True)
    initialize(c)
    ensure_plan_schema(c)
    plan_id = plan_writer.ensure_plan(c, "zd")
    yield c, plan_id
    c.close()


def test_record_itogo_observation_known(plan_conn):
    conn, plan_id = plan_conn
    storage = "<p><strong>Итого: с 01.01.26 по 02.02.26 - 10 рабочих дней</strong></p>"
    obs_id = record_itogo_observation(
        plan_id, "537561928", page_version=1, raw_storage=storage, conn=conn,
    )
    row = conn.execute(
        "SELECT itogo_d1, itogo_d2, itogo_n, quality FROM plan_page_observation WHERE observation_id=?",
        (obs_id,),
    ).fetchone()
    assert tuple(row) == ("01.01.26", "02.02.26", 10, "ok")


def test_record_itogo_observation_missing_is_unknown_not_fabricated(plan_conn):
    """AC-110: отсутствующий исторический «Итого» помечен unknown, не
    выдуман как 01.01.00."""
    conn, plan_id = plan_conn
    obs_id = record_itogo_observation(
        plan_id, "537561928", page_version=4, raw_storage="<p>нет итого</p>", conn=conn,
    )
    row = conn.execute(
        "SELECT itogo_d1, itogo_n, quality FROM plan_page_observation WHERE observation_id=?",
        (obs_id,),
    ).fetchone()
    assert tuple(row) == (None, None, "unknown")


def test_record_itogo_observation_two_observations_not_glued_by_number(plan_conn):
    """Разные наблюдения с совпадающим N не склеиваются: каждое — отдельная строка."""
    conn, plan_id = plan_conn
    storage = "<p><strong>Итого: с 01.01.26 по 02.02.26 - 10 рабочих дней</strong></p>"
    obs1 = record_itogo_observation(plan_id, "537561928", page_version=1, raw_storage=storage, conn=conn)
    obs2 = record_itogo_observation(plan_id, "537561928", page_version=2, raw_storage=storage, conn=conn)
    assert obs1 != obs2
    count = conn.execute("SELECT COUNT(*) FROM plan_page_observation").fetchone()[0]
    assert count == 2
