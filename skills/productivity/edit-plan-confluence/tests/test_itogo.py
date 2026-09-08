from __future__ import annotations

from itogo import apply_itogo, build_itogo_html, compute_itogo_from_csv, format_thousands, patch_itogo
from macro import build_macro_html, macro_span


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
    assert "Трудозатраты: 2 356 человек-часа" in html
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
    assert "2 356" in out
    assert "Загрузка 70%" in out


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
    assert "2 356" in out
