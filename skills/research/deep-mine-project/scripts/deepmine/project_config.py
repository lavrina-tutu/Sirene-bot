"""Load and validate PROJECT.yaml."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .fail import ValidationError
from .paths import overlay_dir, workvault_root

DEFAULT_RATE_RUB_PER_HOUR = 3000
SUPPORTED_SCHEMA_VERSIONS = frozenset({"1.0", "1.1"})


@dataclass
class FollowPolicy:
  mode: str = "same-space-plus-allowed-pmo"
  depth: int = 1
  allowed_spaces: list[str] = field(default_factory=list)
  denylist_title_substrings: list[str] = field(default_factory=list)
  unknown_space: str = "stub"
  max_outbound_pull: int = 24

  @property
  def enabled(self) -> bool:
    return self.mode not in ("off", "disabled", "")


@dataclass
class ContextsConfig:
  charter_body_page_ids: list[str] = field(default_factory=list)
  architecture_themes: list[str] = field(default_factory=lambda: ["architecture", "security"])
  architecture_body_page_ids: list[str] = field(default_factory=list)


@dataclass
class ProjectConfig:
  schema_version: str
  slug: str
  display_name: str
  entity_slug: str
  confluence: dict[str, Any]
  plan: dict[str, Any]
  meetings: dict[str, Any]
  themes: list[str] = field(default_factory=list)
  follow: FollowPolicy = field(default_factory=FollowPolicy)
  contexts: ContextsConfig = field(default_factory=ContextsConfig)

  @property
  def mpp(self) -> dict[str, Any]:
    """Backward-compat alias for ``plan`` (PROJECT.yaml ``mpp:``)."""
    return self.plan

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
  def rate_rub_per_hour(self) -> int:
    raw = self.plan.get("rate_rub_per_hour", DEFAULT_RATE_RUB_PER_HOUR)
    try:
      return int(raw)
    except (TypeError, ValueError):
      return DEFAULT_RATE_RUB_PER_HOUR

  @property
  def gantt_page_id(self) -> str:
    return str(self.plan.get("gantt_page_id") or "")

  @property
  def gantt_instance(self) -> str:
    return str(self.plan.get("gantt_instance") or "")

  @property
  def attachment_page_ids(self) -> list[str]:
    ids: list[str] = [self.root_page_id]
    for seed in self.pmo_seeds:
      pid = str(seed.get("page_id") or "")
      if pid and pid not in ids:
        ids.append(pid)
    gid = self.gantt_page_id
    if gid and gid not in ids:
      ids.append(gid)
    return ids

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


def _parse_follow(raw: Any, space_primary: str) -> FollowPolicy:
  if raw is None:
    return FollowPolicy(allowed_spaces=[space_primary, "PMO"])
  if isinstance(raw, str):
    if raw in ("pmo-from-root", "same-space-plus-allowed-pmo"):
      return FollowPolicy(
        mode="same-space-plus-allowed-pmo",
        allowed_spaces=[space_primary, "PMO"],
      )
    if raw == "off":
      return FollowPolicy(mode="off")
    return FollowPolicy(mode=raw, allowed_spaces=[space_primary, "PMO"])
  if not isinstance(raw, dict):
    return FollowPolicy(allowed_spaces=[space_primary, "PMO"])
  allowed = list(raw.get("allowed_spaces") or [space_primary, "PMO"])
  return FollowPolicy(
    mode=str(raw.get("mode") or "same-space-plus-allowed-pmo"),
    depth=int(raw.get("depth") or 1),
    allowed_spaces=allowed,
    denylist_title_substrings=list(raw.get("denylist_title_substrings") or []),
    unknown_space=str(raw.get("unknown_space") or "stub"),
    max_outbound_pull=int(raw.get("max_outbound_pull") or 24),
  )


def _parse_contexts(raw: Any) -> ContextsConfig:
  if not isinstance(raw, dict):
    return ContextsConfig()
  return ContextsConfig(
    charter_body_page_ids=[str(x) for x in (raw.get("charter_body_page_ids") or [])],
    architecture_themes=[str(x) for x in (raw.get("architecture_themes") or ["architecture", "security"])],
    architecture_body_page_ids=[str(x) for x in (raw.get("architecture_body_page_ids") or [])],
  )


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


def _merge_plan_section(raw: dict[str, Any]) -> dict[str, Any]:
  """``plan:`` wins over legacy ``mpp:``; either key is accepted on input."""
  merged: dict[str, Any] = dict(raw.get("mpp") or {})
  merged.update(raw.get("plan") or {})
  return merged


def validate_project_config(raw: dict[str, Any], *, slug: str | None = None) -> ProjectConfig:
  version = str(raw.get("schema_version") or "")
  if version not in SUPPORTED_SCHEMA_VERSIONS:
    raise ValidationError(f"PROJECT.yaml schema_version must be one of {sorted(SUPPORTED_SCHEMA_VERSIONS)}")
  for key in ("slug", "display_name", "entity_slug", "confluence", "meetings"):
    if key not in raw:
      raise ValidationError(f"PROJECT.yaml missing required field: {key}")
  if "plan" not in raw and "mpp" not in raw:
    raise ValidationError("PROJECT.yaml missing required field: plan")
  if slug and raw["slug"] != slug:
    raise ValidationError(f"PROJECT.yaml slug mismatch: {raw['slug']} != {slug}")
  conf = raw["confluence"]
  for key in ("root_page_id", "root_title", "space_primary"):
    if key not in conf:
      raise ValidationError(f"PROJECT.yaml confluence.{key} required")
  space_primary = str(conf["space_primary"])
  follow_raw = conf.get("follow_outbound")
  return ProjectConfig(
    schema_version=version,
    slug=raw["slug"],
    display_name=raw["display_name"],
    entity_slug=raw["entity_slug"],
    confluence=conf,
    plan=_merge_plan_section(raw),
    meetings=raw["meetings"],
    themes=list(raw.get("themes") or []),
    follow=_parse_follow(follow_raw, space_primary),
    contexts=_parse_contexts(raw.get("contexts")),
  )


def migrate_project_yaml(path: Path) -> bool:
  """Idempotent migration to schema 1.1 with follow object and contexts."""
  if not path.is_file():
    return False
  raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
  changed = False
  if raw.get("schema_version") == "1.0":
    raw["schema_version"] = "1.1"
    changed = True
  conf = raw.setdefault("confluence", {})
  follow = conf.get("follow_outbound")
  if isinstance(follow, str):
    conf["follow_outbound"] = {
      "mode": "same-space-plus-allowed-pmo" if follow == "pmo-from-root" else follow,
      "depth": 1,
      "allowed_spaces": [conf.get("space_primary", "DPAN"), "PMO"],
      "denylist_title_substrings": ["шаблон ПРО", "template ПРО"],
      "unknown_space": "stub",
      "max_outbound_pull": 24,
    }
    changed = True
  elif isinstance(follow, dict) and "depth" not in follow:
    follow["depth"] = 1
    changed = True
  contexts = raw.setdefault("contexts", {})
  if "charter_body_page_ids" not in contexts:
    body_ids: list[str] = []
    for seed in conf.get("pmo_seeds") or []:
      pid = str(seed.get("page_id") or "")
      if pid:
        body_ids.append(pid)
    for task in conf.get("task_pages") or []:
      pid = str(task.get("page_id") or "")
      if pid and pid not in body_ids:
        body_ids.append(pid)
    gantt = raw.get("plan", {}).get("gantt_page_id") or raw.get("mpp", {}).get("gantt_page_id")
    if gantt and str(gantt) not in body_ids:
      body_ids.append(str(gantt))
    contexts["charter_body_page_ids"] = body_ids
    changed = True
  if "architecture_themes" not in contexts:
    contexts["architecture_themes"] = ["architecture", "security"]
    changed = True
  if changed:
    path.write_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8")
  return changed


def default_trisigma_yaml() -> str:
  return """schema_version: "1.1"
slug: TrisigmaFull
display_name: "Полное внедрение AB-платформы Trisigma"
entity_slug: trisigma
confluence:
  root_page_id: "480923430"
  root_title: "Trisigma проект. Пилот. Выполнение проекта"
  space_primary: DPAN
  pmo_seeds:
    - { page_id: "490166551", title: "Бриф", space: PMO }
    - { page_id: "490167911", title: "Устав", space: PMO }
  task_pages:
    - { page_id: "519487958", role: charter_draft, space: PMO }
    - { page_id: "519489611", role: feature_gap }
    - { page_id: "514903239", role: feature_compare }
  follow_outbound:
    mode: same-space-plus-allowed-pmo
    depth: 1
    allowed_spaces: [DPAN, PMO]
    denylist_title_substrings: ["шаблон ПРО", "template ПРО"]
    unknown_space: stub
    max_outbound_pull: 24
plan:
  source: gantt
  gantt_page_id: "519492770"
  gantt_instance: b10931f5-7163-4270-95c4-b8d1ca9d23ac
  rate_rub_per_hour: 3000
  project_title: "Полное внедрение AB-платформы Trisigma"
meetings:
  project_slugs: [trisigma]
contexts:
  charter_body_page_ids:
    - "490166551"
    - "490167911"
    - "519487958"
    - "519492770"
  architecture_themes: [architecture, security]
  architecture_body_page_ids:
    - "514903239"
    - "519489611"
themes:
  - pmo
  - architecture
  - poc-criteria
  - full-rollout
  - security
  - plan
  - meetings
"""
