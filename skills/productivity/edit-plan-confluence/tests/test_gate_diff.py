from __future__ import annotations

from gate_diff import build_diff, is_confirmed


def test_is_confirmed():
    assert is_confirmed("лей")
    assert is_confirmed("пиши")
    assert is_confirmed("да")
    assert not is_confirmed("нет")
    assert not is_confirmed("")


def test_build_diff_contains_warning():
    text = build_diff(
        page_id="519501810",
        title="Test",
        operation="замена",
        had_existing_plan=True,
    )
    assert "заменён целиком" in text
    assert "лей" in text
