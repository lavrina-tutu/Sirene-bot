"""LLM-assisted facts extraction (layer B)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .llm_json import call_json
from .l0 import parse_l0_page
from .paths import SKILL_ROOT, l0_abs

PEOPLE_SCHEMA: dict[str, Any] = {
  "type": "object",
  "title": "people_response",
  "properties": {
    "people": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "fio": {"type": "string"},
          "role": {"type": "string"},
          "source_page_id": {"type": "string"},
          "confidence": {"type": "string"},
        },
        "required": ["fio", "source_page_id", "confidence"],
        "additionalProperties": False,
      },
    },
  },
  "required": ["people"],
  "additionalProperties": False,
}

ASSIGNMENTS_SCHEMA: dict[str, Any] = {
  "type": "object",
  "title": "assignments_response",
  "properties": {
    "assignments": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "text": {"type": "string"},
          "assignee": {"type": "string"},
          "source_page_id": {"type": "string"},
          "confidence": {"type": "string"},
        },
        "required": ["text", "source_page_id", "confidence"],
        "additionalProperties": False,
      },
    },
  },
  "required": ["assignments"],
  "additionalProperties": False,
}


def _prompt_path() -> Path:
  return SKILL_ROOT / "references" / "facts-llm-prompt.md"


def _build_prompt(page_id: str, title: str, body: str) -> str:
  base = ""
  prompt_file = _prompt_path()
  if prompt_file.is_file():
    base = prompt_file.read_text(encoding="utf-8")
  return (
    f"{base}\n\n"
    f"page_id: {page_id}\n"
    f"title: {title}\n\n"
    f"---\n{body[:12000]}\n"
  )


def extract_people_assignments(
  page_id: str,
  page: dict[str, Any],
  workvault: Path,
  *,
  dry_run: bool = False,
) -> dict[str, list[dict[str, Any]]]:
  local_rel = page.get("local_path")
  if not local_rel:
    return {"people": [], "assignments": []}
  l0 = l0_abs(workvault, local_rel)
  if not l0.exists():
    return {"people": [], "assignments": []}
  rec = parse_l0_page(l0, local_path=local_rel)
  if dry_run:
    return {"people": [], "assignments": []}

  prompt = _build_prompt(page_id, rec.title, rec.body)
  people_data = call_json(prompt, PEOPLE_SCHEMA)
  assign_data = call_json(
    prompt + "\n\nИзвлеки только поручения (assignments).",
    ASSIGNMENTS_SCHEMA,
  )
  people = people_data.get("people") or []
  assignments = assign_data.get("assignments") or []
  for item in people:
    item.setdefault("source_page_id", page_id)
    item.setdefault("source_kind", "llm")
  for item in assignments:
    item.setdefault("source_page_id", page_id)
    item.setdefault("source_kind", "llm")
  return {"people": people, "assignments": assignments}
