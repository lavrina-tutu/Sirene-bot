"""Load and validate PROJECT.yaml."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .fail import ValidationError
from .paths import overlay_dir, workvault_root


@dataclass
class ProjectConfig:
  schema_version: str
  slug: str
  display_name: str
  entity_slug: str
  confluence: dict[str, Any]
  mpp: dict[str, Any]
  meetings: dict[str, Any]
  themes: list[str] = field(default_factory=list)

  @property
  def root_page_id(self) -> str:
    return str(self.confluence["root_page_id"])

  @property
  def pmo_seeds(self) -> list[dict[str, str]]:
    return list(self.confluence.get("pmo_seeds") or [])

  @property
  def task_pages(self) -> list[dict[str, Any]]:
    return list(self.confluence.get("task_pages") or [])

  @property
  def meeting_project_slugs(self) -> list[str]:
    return list(self.meetings.get("project_slugs") or [])

  @property
  def tasks(self) -> dict[str, str]:
    """task_id → page_id from optional ``tasks`` map or ``task_pages`` list."""
    result: dict[str, str] = {}
    explicit = self.confluence.get("tasks") or {}
    if isinstance(explicit, dict):
      result.update({str(k): str(v) for k, v in explicit.items()})
    for entry in self.confluence.get("task_pages") or []:
      if not isinstance(entry, dict):
        continue
      page_id = str(entry.get("page_id") or "")
      if not page_id:
        continue
      role = str(entry.get("role") or "")
      if role:
        result[role] = page_id
        if role.endswith("_draft"):
          result[role.removesuffix("_draft")] = page_id
        if role.endswith("_gap"):
          result[role.removesuffix("_gap")] = page_id
    return result


def project_yaml_path(workvault: Path, slug: str) -> Path:
  return overlay_dir(workvault, slug) / "PROJECT.yaml"


def load_project_config(
  slug: str,
  *,
  workvault: str | Path | None = None,
) -> ProjectConfig:
  wv = workvault_root(workvault)
  path = project_yaml_path(wv, slug)
  if not path.exists():
    raise ValidationError(f"PROJECT.yaml not found: {path}")
  raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
  return validate_project_config(raw, slug=slug)


def validate_project_config(raw: dict[str, Any], *, slug: str | None = None) -> ProjectConfig:
  if raw.get("schema_version") != "1.0":
    raise ValidationError("PROJECT.yaml schema_version must be '1.0'")
  for key in ("slug", "display_name", "entity_slug", "confluence", "mpp", "meetings"):
    if key not in raw:
      raise ValidationError(f"PROJECT.yaml missing required field: {key}")
  if slug and raw["slug"] != slug:
    raise ValidationError(f"PROJECT.yaml slug mismatch: {raw['slug']} != {slug}")
  conf = raw["confluence"]
  for key in ("root_page_id", "root_title", "space_primary"):
    if key not in conf:
      raise ValidationError(f"PROJECT.yaml confluence.{key} required")
  return ProjectConfig(
    schema_version=raw["schema_version"],
    slug=raw["slug"],
    display_name=raw["display_name"],
    entity_slug=raw["entity_slug"],
    confluence=conf,
    mpp=raw["mpp"],
    meetings=raw["meetings"],
    themes=list(raw.get("themes") or []),
  )


def default_trisigma_yaml() -> str:
  return """schema_version: "1.0"
slug: TrisigmaFull
display_name: "Полное внедрение AB-платформы Trisigma"
entity_slug: trisigma
confluence:
  root_page_id: "493477568"
  root_title: "Trisigma проект. Пилот. Выполнение проекта"
  space_primary: DPAN
  pmo_seeds:
    - { page_id: "490166551", title: "Бриф", space: PMO }
    - { page_id: "490167911", title: "Устав", space: PMO }
  task_pages:
    - { page_id: "519487958", role: charter_draft, space: PMO }
    - { page_id: "519489611", role: feature_gap }
    - { page_id: "514903239", role: feature_compare }
  follow_outbound: pmo-from-root
mpp:
  expected_name: "Антибот внедрение Отели + исследование внедрение вертикали 260925"
  project_title: "Полное внедрение AB-платформы Trisigma"
meetings:
  project_slugs: [trisigma]
themes:
  - pmo
  - architecture
  - poc-criteria
  - full-rollout
  - security
  - plan
  - meetings
"""
