"""Table extract from L0 markdown/HTML (A1)."""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

from deepmine.digest_validate import l0_has_table
from deepmine.table_extract import (
  extract_tables,
  extract_tables_from_body,
  parse_html_tables,
  parse_markdown_tables,
)

FIXTURES = Path(__file__).parent / "fixtures" / "mini_l0"


def test_l0_has_table_markdown():
  body = FIXTURES.joinpath("table_page", "index.md").read_text(encoding="utf-8")
  assert l0_has_table(body)


def test_l0_has_table_plain_page():
  body = FIXTURES.joinpath("child", "index.md").read_text(encoding="utf-8")
  assert not l0_has_table(body)


def test_parse_markdown_tables():
  body = FIXTURES.joinpath("table_page", "index.md").read_text(encoding="utf-8")
  tables = parse_markdown_tables(body.split("---", 2)[-1])
  assert len(tables) == 1
  assert tables[0][0] == ["Фича", "Чего не хватает", "Сложность"]
  assert len(tables[0]) == 4


def test_parse_html_tables():
  html = "<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>"
  tables = parse_html_tables(html)
  assert len(tables) == 1
  assert tables[0] == [["A", "B"], ["1", "2"]]


def test_extract_tables_writes_csv(tmp_path: Path):
  l0 = FIXTURES / "table_page" / "index.md"
  out = tmp_path / "extracts"
  written = extract_tables(l0, out, "514903239", "feature_compare")
  assert len(written) == 1
  assert written[0].name == "514903239__feature_compare.csv"
  with written[0].open(encoding="utf-8") as handle:
    rows = list(csv.reader(handle))
  assert rows[0][0] == "Фича"
  assert rows[1][0] == "Anti-bot API"


def test_extract_tables_from_body_multiple(tmp_path: Path):
  body = """
| H1 | H2 |
| --- | --- |
| a | b |

<table><tr><td>x</td><td>y</td></tr></table>
"""
  tables = extract_tables_from_body(body)
  assert len(tables) == 2
