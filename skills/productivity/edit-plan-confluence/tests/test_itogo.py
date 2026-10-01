from __future__ import annotations

from itogo import (
    apply_itogo,
    build_itogo_html,
    compute_itogo_from_csv,
    format_thousands,
    patch_itogo,
    strip_trudozatraty,
)
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
