"""Extract markdown/HTML tables from L0 pages to CSV (A1). No agent -p, no ConfluenceSync import."""
from __future__ import annotations

import csv
import re
from pathlib import Path

from bs4 import BeautifulSoup

from .digest_validate import l0_has_table

_MD_TABLE_LINE = re.compile(r"^\s*\|.+\|.+\|\s*$", re.MULTILINE)
_MD_TABLE_SEP = re.compile(r"^\s*\|[-:\s|]+\|\s*$", re.MULTILINE)


def _strip_frontmatter(text: str) -> str:
  if text.startswith("---"):
    end = text.find("\n---", 3)
    if end != -1:
      return text[end + 4 :].lstrip("\n")
  return text


def parse_markdown_tables(body: str) -> list[list[list[str]]]:
  """Parse pipe markdown tables from body (after frontmatter strip)."""
  tables: list[list[list[str]]] = []
  lines = body.splitlines()
  i = 0
  while i < len(lines):
    if not _MD_TABLE_LINE.match(lines[i]):
      i += 1
      continue
    block: list[str] = []
    while i < len(lines) and _MD_TABLE_LINE.match(lines[i]):
      block.append(lines[i])
      i += 1
    rows: list[list[str]] = []
    for line in block:
      if _MD_TABLE_SEP.match(line):
        continue
      cells = [c.strip() for c in line.strip().strip("|").split("|")]
      if cells:
        rows.append(cells)
    if rows:
      tables.append(rows)
  return tables


def parse_html_tables(body: str) -> list[list[list[str]]]:
  """Parse HTML <table> elements via BeautifulSoup."""
  if "<table" not in body.lower():
    return []
  soup = BeautifulSoup(body, "html.parser")
  tables: list[list[list[str]]] = []
  for table in soup.find_all("table"):
    rows: list[list[str]] = []
    for tr in table.find_all("tr"):
      cells = [cell.get_text(strip=True) for cell in tr.find_all(["td", "th"])]
      if cells:
        rows.append(cells)
    if rows:
      tables.append(rows)
  return tables


def extract_tables_from_body(body: str) -> list[list[list[str]]]:
  """All tables in page body (markdown + HTML)."""
  body = _strip_frontmatter(body)
  return parse_markdown_tables(body) + parse_html_tables(body)


def _csv_filename(page_id: str, slug: str, index: int, total: int) -> str:
  if total <= 1:
    return f"{page_id}__{slug}.csv"
  return f"{page_id}__{slug}__{index}.csv"


def write_table_csv(table: list[list[str]], path: Path) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  with path.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.writer(handle)
    writer.writerows(table)


def extract_tables(
  l0_path: Path,
  out_dir: Path,
  page_id: str,
  slug: str,
) -> list[Path]:
  """Write one CSV per table in L0 page. Returns written paths (may be empty)."""
  text = l0_path.read_text(encoding="utf-8")
  tables = extract_tables_from_body(text)
  out_dir.mkdir(parents=True, exist_ok=True)
  written: list[Path] = []
  for index, table in enumerate(tables):
    name = _csv_filename(page_id, slug, index, len(tables))
    path = out_dir / name
    write_table_csv(table, path)
    written.append(path)
  return written


def task_id_for_entry(entry: dict) -> str:
  """Pack/collect task key from task_pages entry."""
  role = str(entry.get("role") or "").strip()
  if role:
    return role
  return str(entry.get("page_id") or "")


def extract_for_task_pages(
  cfg,
  overlay: Path,
  workvault: Path,
  manifest,
) -> list[Path]:
  """Extract tables for all task_pages into docs/_inbox/<role>/extracts/."""
  from .fail import ValidationError

  all_written: list[Path] = []
  for entry in cfg.task_pages:
    page_id = str(entry.get("page_id") or "")
    if not page_id:
      continue
    task_id = task_id_for_entry(entry)
    page = manifest.pages.get(page_id)
    if page is None:
      raise ValidationError(
        f"task_pages role={task_id} page_id={page_id} not in MANIFEST — "
        "добавь в task_pages и collect"
      )
    local_path = str(page.get("local_path") or "")
    if not local_path:
      continue
    l0_path = workvault / local_path
    if not l0_path.is_file():
      continue
    out_dir = overlay / "docs" / "_inbox" / task_id / "extracts"
    written = extract_tables(l0_path, out_dir, page_id, task_id)
    all_written.extend(written)
  return all_written
