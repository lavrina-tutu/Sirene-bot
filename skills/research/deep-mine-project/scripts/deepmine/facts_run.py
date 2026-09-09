"""Orchestrate facts.json build (layer B)."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .facts_llm import extract_people_assignments
from .facts_script import build_script_only
from .fail import ContextError, context_failed
from .paths import FACTS_JSON
from .project_config import ProjectConfig


def utc_now_iso() -> str:
  return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def facts_sha(data: dict[str, Any]) -> str:
  payload = {
    "script_only": data.get("script_only") or {},
    "llm_assisted": data.get("llm_assisted") or {},
  }
  return hashlib.sha256(
    json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
  ).hexdigest()


def _merge_llm(
  script_only: dict[str, Any],
  llm_assisted: dict[str, Any],
) -> dict[str, Any]:
  """Numbers from llm do not override script_only."""
  script_sums = {s.get("label") for s in script_only.get("sums") or []}
  filtered_sums = [
    s for s in llm_assisted.get("sums") or []
    if s.get("label") not in script_sums
  ]
  return {
    "people": llm_assisted.get("people") or [],
    "assignments": llm_assisted.get("assignments") or [],
    "sums": filtered_sums,
  }


def write_facts_json(data: dict[str, Any], overlay: Path) -> Path:
  path = overlay / FACTS_JSON
  path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
  return path


def write_rejected_facts(overlay: Path, raw: Any, errors: list[str]) -> Path:
  path = overlay / "facts.rejected.json"
  path.write_text(
    json.dumps({"raw": raw, "errors": errors}, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
  )
  return path


def run_facts(
  cfg: ProjectConfig,
  overlay: Path,
  workvault: Path,
  pages: dict[str, dict[str, Any]],
  *,
  skip_llm: bool = False,
  dry_run: bool = False,
  only_page_ids: set[str] | None = None,
) -> dict[str, Any]:
  script_only = build_script_only(cfg, pages, overlay, workvault)
  people: list[dict[str, Any]] = []
  assignments: list[dict[str, Any]] = []

  existing_path = overlay / FACTS_JSON
  if existing_path.is_file() and only_page_ids:
    try:
      existing = json.loads(existing_path.read_text(encoding="utf-8"))
      llm = existing.get("llm_assisted") or {}
      people = [
        p for p in llm.get("people") or []
        if p.get("source_page_id") not in only_page_ids
      ]
      assignments = [
        a for a in llm.get("assignments") or []
        if a.get("source_page_id") not in only_page_ids
      ]
    except (json.JSONDecodeError, OSError):
      pass

  if not skip_llm and not dry_run:
    targets = only_page_ids if only_page_ids else set(pages.keys())
    for page_id in sorted(targets):
      page = pages.get(page_id)
      if not page:
        continue
      try:
        result = extract_people_assignments(page_id, page, workvault)
        people.extend(result.get("people") or [])
        assignments.extend(result.get("assignments") or [])
      except Exception as exc:
        write_rejected_facts(overlay, {"page_id": page_id}, [str(exc)])
        context_failed(f"facts llm_assisted failed for {page_id}: {exc}")

  llm_assisted = _merge_llm(script_only, {"people": people, "assignments": assignments})
  data = {
    "schema_version": "1.0",
    "slug": cfg.slug,
    "generated_at": utc_now_iso(),
    "script_only": script_only,
    "llm_assisted": llm_assisted,
  }
  data["facts_sha"] = facts_sha(data)

  if not dry_run:
    write_facts_json(data, overlay)
  return data
