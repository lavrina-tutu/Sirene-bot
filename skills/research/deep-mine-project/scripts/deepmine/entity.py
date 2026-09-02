"""Entity pointer → pointers/entity.md (paths only, no copies)."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


ENTITY_FILES = (
  "card.md",
  "context.md",
  "risks.md",
  "contract_vendor.md",
  "status_snapshot.md",
  "protocol.md",
)


def entity_paths(workvault: Path, entity_slug: str) -> list[tuple[str, Path]]:
  base = workvault / "Entities" / entity_slug
  found: list[tuple[str, Path]] = []
  for name in ENTITY_FILES:
    path = base / name
    if path.exists():
      found.append((name, path))
  pages_dir = base / "Pages"
  if pages_dir.is_dir():
    for page in sorted(pages_dir.glob("*.md")):
      found.append((f"Pages/{page.name}", page))
  return found


def write_entity_pointer(workvault: Path, overlay: Path, entity_slug: str) -> Path:
  out = overlay / "pointers" / "entity.md"
  out.parent.mkdir(parents=True, exist_ok=True)
  now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
  paths = entity_paths(workvault, entity_slug)
  lines = [
    "---",
    "kind: entity_pointer",
    f"entity_slug: {entity_slug}",
    f"generated_at: {now}",
    "---",
    "",
    f"# Указатель сущности `{entity_slug}`",
    "",
    "Пути на канон в `Entities/`. Тела файлов не копируются.",
    "",
    "| Файл | Путь |",
    "|---|---|",
  ]
  for rel_name, path in paths:
    rel = path.relative_to(workvault)
    lines.append(f"| {rel_name} | `Entities/{entity_slug}/{rel_name}` → `{rel}` |")
  out.write_text("\n".join(lines) + "\n", encoding="utf-8")
  return out
