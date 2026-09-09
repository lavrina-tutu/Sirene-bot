"""Charter batch orchestration with cache (J7)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .context_prompt import batch_prompt, narrow_input
from .context_schema import ARCHITECTURE_THEME_SCHEMAS, CHARTER_BATCH_FIELDS, CHARTER_BATCH_SCHEMAS
from .context_validate import raise_on_errors, validate_batch
from .llm_json import CONTEXT_MODEL, call_json
from .project_config import ProjectConfig


def batch_input_hash(kind: str, batch_key: str, narrow: str) -> str:
  payload = f"{kind}:{batch_key}:{narrow}"
  return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _cache_path(overlay: Path, key: str) -> Path:
  return overlay / "context_cache" / f"{key}.json"


def _load_cache(overlay: Path, key: str) -> dict[str, Any] | None:
  path = _cache_path(overlay, key)
  if path.is_file():
    try:
      return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
      return None
  return None


def _save_cache(overlay: Path, key: str, data: dict[str, Any]) -> None:
  cache_dir = overlay / "context_cache"
  cache_dir.mkdir(parents=True, exist_ok=True)
  _cache_path(overlay, key).write_text(
    json.dumps(data, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
  )


def run_charter_batches(
  cfg: ProjectConfig,
  overlay: Path,
  graph: dict[str, Any],
  facts: dict[str, Any],
  pages: dict[str, Any],
  workvault: Path,
  *,
  dry_run: bool = False,
  llm_calls: list[str] | None = None,
) -> list[dict[str, Any]]:
  narrow = narrow_input("charter", cfg, graph, facts, pages, workvault)
  results: list[dict[str, Any]] = []
  for batch_num in range(1, 6):
    fields = CHARTER_BATCH_FIELDS[batch_num]
    key = batch_input_hash("charter", str(batch_num), narrow)
    cached = _load_cache(overlay, key)
    if cached:
      results.append(cached)
      continue
    if dry_run:
      results.append({"batch": batch_num, "sections": []})
      continue
    prompt = batch_prompt("charter", batch_num, narrow, fields)
    schema = CHARTER_BATCH_SCHEMAS[batch_num]
    if llm_calls is not None:
      llm_calls.append(f"charter_batch_{batch_num}")
    data = call_json(prompt, schema, model=CONTEXT_MODEL)
    errors = validate_batch(data, schema, required_fields=fields)
    raise_on_errors("charter", overlay, data, errors)
    _save_cache(overlay, key, data)
    results.append(data)
  return results


def run_architecture_batches(
  cfg: ProjectConfig,
  overlay: Path,
  graph: dict[str, Any],
  facts: dict[str, Any],
  pages: dict[str, Any],
  workvault: Path,
  *,
  dry_run: bool = False,
  llm_calls: list[str] | None = None,
) -> list[dict[str, Any]]:
  narrow = narrow_input("architecture", cfg, graph, facts, pages, workvault)
  results: list[dict[str, Any]] = []
  for theme in cfg.contexts.architecture_themes:
    key = batch_input_hash("architecture", theme, narrow)
    cached = _load_cache(overlay, key)
    if cached:
      results.append(cached)
      continue
    if dry_run:
      results.append({"theme": theme, "sections": []})
      continue
    schema = ARCHITECTURE_THEME_SCHEMAS.get(theme, ARCHITECTURE_THEME_SCHEMAS["architecture"])
    prompt = batch_prompt("architecture", 0, narrow, [theme])
    if llm_calls is not None:
      llm_calls.append(f"architecture_{theme}")
    data = call_json(prompt, schema, model=CONTEXT_MODEL)
    errors = validate_batch(data, schema)
    raise_on_errors("architecture", overlay, data, errors)
    _save_cache(overlay, key, data)
    results.append(data)
  return results
