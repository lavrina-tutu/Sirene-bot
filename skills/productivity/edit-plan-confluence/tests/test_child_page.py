from __future__ import annotations

from child_page import build_child_storage, default_child_title


def test_default_child_title():
    t = default_child_title("Родитель")
    assert t.startswith("Родитель. План ")
    assert "План" in t


def test_build_child_storage():
    s = build_child_storage("<p>itogo</p>", "<p>macro</p>")
    assert s.index("itogo") < s.index("macro")
