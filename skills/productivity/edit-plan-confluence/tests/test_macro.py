from __future__ import annotations

from macro import build_macro_html, find_macro, new_macro_ids


SAMPLE = (
    '<p><ac:structured-macro ac:name="gantt-chart-planner" ac:schema-version="1" '
    'ac:macro-id="25b9de75-cb34-4cc1-a17a-c314457308b2">'
    '<ac:parameter ac:name="id">b10931f5a1b24c0d9e8f7a6b5c4d3e2f</ac:parameter>'
    '<ac:parameter ac:name="hash">76c0f2e1a9b84d3c2e1f0a9b8c7d6e5f</ac:parameter>'
    "</ac:structured-macro></p>"
)


def test_find_macro():
    m = find_macro(SAMPLE)
    assert m is not None
    assert m.macro_id == "25b9de75-cb34-4cc1-a17a-c314457308b2"
    assert m.attachment_name == "gantt-chart-25b9de75-cb34-4cc1-a17a-c314457308b2.json"


def test_new_macro_ids_unique():
    a = new_macro_ids()
    b = new_macro_ids()
    assert a != b
    assert a[0] != "25b9de75-cb34-4cc1-a17a-c314457308b2"


def test_build_macro_html():
    html = build_macro_html("mid", "pid", "phash")
    assert 'ac:macro-id="mid"' in html
    assert "gantt-chart-planner" in html
