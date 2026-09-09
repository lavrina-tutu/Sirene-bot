"""Validate context batches and assembled markdown (J4-J6)."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .fail import ContextError, context_failed
from .llm_json import strip_preamble

_JOURNAL_RE = re.compile(r"Digest записан|Пишу\.\.\.|журнал", re.IGNORECASE)


def validate_batch(
  data: dict[str, Any],
  schema: dict[str, Any],
  *,
  required_fields: list[str] | None = None,
) -> list[str]:
  errors: list[str] = []
  if "sections" not in data and "batch" not in data and "theme" not in data:
    errors.append("missing sections")
    return errors
  sections = data.get("sections") or []
  if not sections:
    errors.append("empty sections")
  for section in sections:
    if not section.get("source_page_id"):
      errors.append(f"missing source_page_id for {section.get('field')}")
    content = str(section.get("content") or "")
    if _JOURNAL_RE.search(content):
      errors.append(f"journal leak in {section.get('field')}")
  if required_fields:
    present = {s.get("field") for s in sections}
    for field in required_fields:
      if field not in present:
        errors.append(f"missing required field: {field}")
  return errors


def validate_assembled_md(body: str) -> list[str]:
  errors: list[str] = []
  if _JOURNAL_RE.search(body):
    errors.append("journal preamble in assembled md")
  if not body.strip().startswith("## Источники"):
    errors.append("body must start with ## Источники")
  return errors


def write_rejected(overlay: Path, kind: str, raw: Any, errors: list[str]) -> Path:
  path = overlay / f"{kind}-context.rejected.json"
  path.write_text(
    json.dumps({"raw": raw, "errors": errors}, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
  )
  return path


def raise_on_errors(kind: str, overlay: Path, raw: Any, errors: list[str]) -> None:
  if errors:
    write_rejected(overlay, kind, raw, errors)
    context_failed(f"{kind} context validation failed: {'; '.join(errors)}")
