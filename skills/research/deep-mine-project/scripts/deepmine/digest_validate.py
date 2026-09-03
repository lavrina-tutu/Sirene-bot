"""Digest body contract validation (A0): reject compressor journal, require facts/tables."""
from __future__ import annotations

import re
from typing import Literal

DigestStatus = Literal["ok", "rejected"]

JOURNAL_PATTERNS: list[re.Pattern[str]] = [
  re.compile(r"сжал\s+до", re.IGNORECASE),
  re.compile(r"%\s*от\s*L0", re.IGNORECASE),
  re.compile(r"Digest\s+записан", re.IGNORECASE),
  re.compile(r"Сначала\s+посмотрю", re.IGNORECASE),
  re.compile(r"Создаю\s+digest", re.IGNORECASE),
  re.compile(r"Самопроверка\s+инвентаря", re.IGNORECASE),
]

AUTHOR_INSTRUCTION_PATTERNS: list[re.Pattern[str]] = [
  re.compile(r"не\s+копировать", re.IGNORECASE),
  re.compile(r"уточнить\s+до\s+ПК", re.IGNORECASE),
]

_YAML_IN_BODY = re.compile(
  r"(?:^|\n)(?:schema_version|kind|slug|page_id|source_sha|generated_by)\s*:",
  re.IGNORECASE,
)

_MD_TABLE_LINE = re.compile(r"^\s*\|.+\|.+\|\s*$", re.MULTILINE)
_MD_TABLE_SEP = re.compile(r"^\s*\|[-:\s|]+\|\s*$", re.MULTILINE)
_CSV_EXTRACT_REF = re.compile(r"extracts/[^\s`]+\.csv", re.IGNORECASE)
_L0_HTML_TABLE = re.compile(r"<table\b", re.IGNORECASE)
_L0_MD_TABLE = re.compile(r"^\s*\|.+\|.+\|\s*$", re.MULTILINE)


def has_journal_text(body: str) -> bool:
  for pattern in JOURNAL_PATTERNS:
    if pattern.search(body):
      return True
  return False


def has_author_instructions(body: str) -> bool:
  for pattern in AUTHOR_INSTRUCTION_PATTERNS:
    if pattern.search(body):
      return True
  return False


def yaml_dump_in_body(body: str) -> bool:
  """Detect YAML frontmatter fields dumped inside digest body."""
  return bool(_YAML_IN_BODY.search(body))


def has_markdown_table(body: str) -> bool:
  if not _MD_TABLE_LINE.search(body):
    return False
  return bool(_MD_TABLE_SEP.search(body))


def has_csv_extract_ref(body: str) -> bool:
  return bool(_CSV_EXTRACT_REF.search(body))


def l0_has_table(l0_body: str) -> bool:
  if _L0_HTML_TABLE.search(l0_body):
    return True
  if _MD_TABLE_LINE.search(l0_body) and _MD_TABLE_SEP.search(l0_body):
    return True
  return False


def validate_digest_body(
  body: str,
  *,
  l0_body: str | None = None,
  require_table_if_l0: bool = True,
) -> DigestStatus:
  """Return ``ok`` or ``rejected`` (fail-loud callers raise on rejected)."""
  if has_journal_text(body):
    return "rejected"
  if yaml_dump_in_body(body):
    return "rejected"
  if has_author_instructions(body):
    return "rejected"
  if require_table_if_l0 and l0_body is not None and l0_has_table(l0_body):
    if not has_markdown_table(body) and not has_csv_extract_ref(body):
      return "rejected"
  return "ok"


def rejection_reason(body: str, *, l0_body: str | None = None) -> str:
  if has_journal_text(body):
    return "digest body contains compressor journal phrases"
  if yaml_dump_in_body(body):
    return "digest body contains YAML frontmatter dump"
  if has_author_instructions(body):
    return "digest body contains author instructions (belongs in brief, not digest)"
  if l0_body is not None and l0_has_table(l0_body):
    if not has_markdown_table(body) and not has_csv_extract_ref(body):
      return "L0 has table but digest lacks markdown table or CSV extract reference"
  return "digest body failed contract validation"
